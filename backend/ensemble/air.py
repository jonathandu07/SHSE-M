# backend/ensemble/air.py
# Données & calculs "Air" (gaz de travail = air ambiant)
#
# Objectif :
# - Fournir un maximum d'informations exploitables (RDM / thermique / écoulements / combustion)
# - Tenir compte : composition (N2/O2/Ar/CO2), altitude, pression, température, humidité
# - Rester autonome (stdlib) + option CoolProp si présent
#
# Références (pour validation des constantes / équations) :
# - US Standard Atmosphere 1976 (couches + formules) via "Formulae and code" : Jim Hawley (PDF)
#   https://jimhawley.ca/pdf/atmosphere.pdf
# - Composition air sec + masse molaire : EngineeringToolbox
#   https://www.engineeringtoolbox.com/molecular-mass-air-d_679.html
# - Humidity ratio x = 0.62198 * pw / (p - pw) : EngineeringToolbox
#   https://www.engineeringtoolbox.com/humidity-ratio-air-d_686.html
# - Pression de vapeur saturante (Tetens) : "Dew point and VPD calculations"
#   https://mkt-toolbox.com/Calculations/DewpointCalculations.pdf
# - Viscosité dynamique air (Sutherland) : constants usuelles (mu = 1.458e-6 * T^(3/2)/(T+110.4))
#   présentes aussi dans le code ISA de Jim Hawley.
# - Masses molaires des constituants : NIST WebBook (N2/O2/Ar/CO2)
#   https://webbook.nist.gov/

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt
from typing import Dict, Optional, Tuple

# =========================
# Constantes fondamentales
# =========================

# Universel
R_UNIV = 8.314462618  # J/(mol*K)
K_B = 1.380649e-23  # J/K

# Atmosphère standard (ISA / US Std Atmos 1976) - constantes "classiques"
G0 = 9.80665  # m/s² (gravité standard)
EARTH_RADIUS_M = 6_356_766.0  # m (rayon effectif ISA, geopotential) (Jim Hawley)
P0 = 101_325.0  # Pa (niveau mer)
T0 = 288.15  # K  (niveau mer)
R_DRY = 287.053  # J/(kg*K) air sec (Jim Hawley / ISA)
GAMMA_DRY = 1.4  # air sec (approx)
M_DRY = R_UNIV / R_DRY  # kg/mol => ~0.0289647 kg/mol

# Eau (vapeur)
M_WV = 0.01801528  # kg/mol (valeur standard)
R_WV = R_UNIV / M_WV  # ~461.5 J/(kg*K)

# Psychrométrie / approximations usuelles
EPSILON = 0.62198  # = M_WV / M_DRY (approx), utilisé dans w = eps*e/(p-e)
PR_AIR_DEFAULT = 0.71  # nombre de Prandtl typique pour l'air (ordre de grandeur)

# Viscosité (Sutherland) : mu(T) = 1.458e-6 * T^(3/2) / (T + 110.4)
# (constantes standard ISA, cf. Jim Hawley)
SUTH_MU_C1 = 1.458e-6  # kg/(m*s*sqrt(K)) => formule compacte
SUTH_MU_S = 110.4  # K

# =========================
# Composition de l'air sec
# =========================
# Valeurs "air sec" typiques (EngineeringToolbox)
# N2 78.084%, O2 20.946%, Ar 0.934%, CO2 ~0.0412% (≈ 412 ppm, variable)
# On autorise un CO2_ppm paramétrable, puis on renormalise surtout N2.

MOLAR_MASS = {
    "N2": 0.0280134,  # kg/mol (NIST)
    "O2": 0.0319988,  # kg/mol (NIST)
    "Ar": 0.0399480,  # kg/mol (NIST)
    "CO2": 0.0440095,  # kg/mol (NIST)
    "H2O": M_WV,
}

DEFAULT_DRY_MOLE_FRACTIONS = {
    "N2": 0.78084,
    "O2": 0.20946,
    "Ar": 0.00934,
    "CO2": 0.000412,  # ~412 ppm (modifiable)
}


def dry_air_mole_fractions(co2_ppm: float = 420.0) -> Dict[str, float]:
    """
    Renvoie les fractions molaires d'air sec (N2/O2/Ar/CO2) en ajustant CO2.
    Hypothèse : O2 et Ar constants, CO2 variable, le reste sur N2.

    Args:
        co2_ppm: ppmv de CO2 (ex: 420 ppm).
    """
    if co2_ppm < 0:
        raise ValueError("co2_ppm doit être >= 0.")
    y = dict(DEFAULT_DRY_MOLE_FRACTIONS)
    y_co2 = co2_ppm * 1e-6
    # Conserver O2 et Ar, ajuster N2
    y["CO2"] = y_co2
    fixed = y["O2"] + y["Ar"] + y["CO2"]
    if fixed >= 1.0:
        raise ValueError("CO2 trop élevé : somme des fractions >= 1.")
    y["N2"] = 1.0 - fixed
    return y


def mixture_molar_mass_from_mole_fractions(y: Dict[str, float]) -> float:
    """Masse molaire du mélange : M = sum(y_i * M_i)."""
    s = 0.0
    for k, yi in y.items():
        if yi < 0:
            raise ValueError(f"Fraction molaire négative pour {k}.")
        if k not in MOLAR_MASS:
            raise KeyError(f"Masse molaire inconnue pour {k}.")
        s += yi * MOLAR_MASS[k]
    return s


def oxygen_mass_fraction_in_dry_air(co2_ppm: float = 420.0) -> float:
    """
    Fraction massique d'O2 dans l'air sec.
    Utile pour combustion / stœchiométrie.
    """
    y = dry_air_mole_fractions(co2_ppm=co2_ppm)
    Mmix = mixture_molar_mass_from_mole_fractions(y)
    return (y["O2"] * MOLAR_MASS["O2"]) / Mmix


# =========================
# Atmosphère standard (ISA)
# =========================

@dataclass(frozen=True)
class AtmosphereLayer:
    """Couche ISA en altitude géopotentielle H (m)."""
    H_base_m: float
    T_base_K: float
    p_base_Pa: float
    lapse_K_per_m: float  # dT/dH (K/m)


# Définition couches (bornes en altitude géopotentielle), conforme au code ISA de Jim Hawley.
# Bornes : 0, 11, 20, 32, 47, 51, 71, 85 km
# Lapses : -6.5, 0, +1.0, +2.8, 0, -2.8, -2.0 K/km
_ISA_BOUNDS_M = (0.0, 11_000.0, 20_000.0, 32_000.0, 47_000.0, 51_000.0, 71_000.0, 85_000.0)
_ISA_LAPSES = (-0.0065, 0.0, 0.0010, 0.0028, 0.0, -0.0028, -0.0020)


def geometric_to_geopotential(h_m: float) -> float:
    """
    Convertit altitude géométrique h -> altitude géopotentielle H.
    Formule : H = Re * h / (Re + h)
    """
    if h_m < -500.0:
        raise ValueError("Altitude trop basse (h_m < -500 m).")
    return EARTH_RADIUS_M * h_m / (EARTH_RADIUS_M + h_m)


def geopotential_to_geometric(H_m: float) -> float:
    """Inverse : h = Re * H / (Re - H)."""
    if H_m >= EARTH_RADIUS_M:
        raise ValueError("H_m doit être < EARTH_RADIUS_M.")
    return EARTH_RADIUS_M * H_m / (EARTH_RADIUS_M - H_m)


def _build_isa_layers() -> Tuple[AtmosphereLayer, ...]:
    """
    Construit les couches ISA avec p_base calculée aux frontières,
    en utilisant les relations hydrostatiques standard.
    """
    layers = []
    # Conditions base mer
    H0 = _ISA_BOUNDS_M[0]
    T_base = T0
    p_base = P0

    layers.append(AtmosphereLayer(H_base_m=H0, T_base_K=T_base, p_base_Pa=p_base, lapse_K_per_m=_ISA_LAPSES[0]))

    for i in range(1, len(_ISA_BOUNDS_M) - 0):  # on calcule p/T base de chaque frontière
        H_prev = _ISA_BOUNDS_M[i - 1]
        H_cur = _ISA_BOUNDS_M[i]
        L_prev = _ISA_LAPSES[i - 1]

        # avancer de H_prev -> H_cur
        if abs(L_prev) < 1e-12:
            # isotherme
            T_cur = T_base
            p_cur = p_base * exp(-G0 * (H_cur - H_prev) / (R_DRY * T_base))
        else:
            T_cur = T_base + L_prev * (H_cur - H_prev)
            p_cur = p_base * (T_cur / T_base) ** (-G0 / (R_DRY * L_prev))

        # préparer couche suivante (si existe)
        if i < len(_ISA_LAPSES):
            L_cur = _ISA_LAPSES[i]
        else:
            L_cur = 0.0

        layers.append(AtmosphereLayer(H_base_m=H_cur, T_base_K=T_cur, p_base_Pa=p_cur, lapse_K_per_m=L_cur))

        T_base, p_base = T_cur, p_cur

        if i == len(_ISA_BOUNDS_M) - 1:
            break

    # On a une couche par frontière. On en garde jusqu'à 85 km inclus.
    return tuple(layers)


ISA_LAYERS = _build_isa_layers()


def isa_dry_temperature_pressure(altitude_m: float, use_geopotential: bool = True) -> Tuple[float, float]:
    """
    Température & pression ISA (air sec) en fonction de l'altitude.

    Args:
        altitude_m: altitude géométrique (m)
        use_geopotential: si True, conversion h->H pour coller ISA
    Returns:
        (T_K, p_Pa)
    """
    if use_geopotential:
        H = geometric_to_geopotential(altitude_m)
    else:
        H = altitude_m

    if H < _ISA_BOUNDS_M[0]:
        H = _ISA_BOUNDS_M[0]
    if H > _ISA_BOUNDS_M[-1]:
        raise ValueError("Altitude au-delà du domaine ISA simplifié (85 km).")

    # trouver la couche active : dernière base <= H
    layer = ISA_LAYERS[0]
    for L in ISA_LAYERS:
        if L.H_base_m <= H:
            layer = L
        else:
            break

    dH = H - layer.H_base_m
    Lapse = layer.lapse_K_per_m
    if abs(Lapse) < 1e-12:
        T = layer.T_base_K
        p = layer.p_base_Pa * exp(-G0 * dH / (R_DRY * T))
    else:
        T = layer.T_base_K + Lapse * dH
        p = layer.p_base_Pa * (T / layer.T_base_K) ** (-G0 / (R_DRY * Lapse))

    return T, p


def isa_density(p_Pa: float, T_K: float, R_spec: float = R_DRY) -> float:
    """Densité idéale : rho = p / (R*T)."""
    if T_K <= 0:
        raise ValueError("T_K doit être > 0.")
    if p_Pa <= 0:
        raise ValueError("p_Pa doit être > 0.")
    return p_Pa / (R_spec * T_K)


# =========================
# Humidité : vapeur saturante, RH, dew point
# =========================

def saturation_vapor_pressure_Pa_Tetens(T_C: float) -> float:
    """
    Pression de vapeur saturante (sur eau liquide) via formule de Tetens (approx).
    e_s(hPa) = 6.1078 * exp( 17.269*T / (237.3 + T) )
    puis conversion hPa -> Pa.

    Domaine pratique : ~[-40°C, +50°C] (usage courant).
    Source : DewpointCalculations.pdf
    """
    e_hPa = 6.1078 * exp((17.269 * T_C) / (237.3 + T_C))
    return e_hPa * 100.0


def vapor_pressure_from_RH(P_Pa: float, T_C: float, RH: float) -> float:
    """e = RH * e_s(T). RH dans [0,1]."""
    if not (0.0 <= RH <= 1.0):
        raise ValueError("RH doit être dans [0,1].")
    es = saturation_vapor_pressure_Pa_Tetens(T_C)
    e = RH * es
    # éviter e >= P
    return min(e, 0.99 * P_Pa)


def humidity_ratio_w(P_Pa: float, e_Pa: float) -> float:
    """
    Humidity ratio (rapport massique vapeur / air sec) :
    w = 0.62198 * e / (P - e)
    Source : EngineeringToolbox humidity ratio.
    """
    if P_Pa <= 0:
        raise ValueError("P_Pa doit être > 0.")
    if e_Pa < 0:
        raise ValueError("e_Pa doit être >= 0.")
    if e_Pa >= P_Pa:
        raise ValueError("e_Pa doit être < P_Pa.")
    return EPSILON * e_Pa / (P_Pa - e_Pa)


def specific_humidity_q(P_Pa: float, e_Pa: float) -> float:
    """
    Spécific humidity q (fraction massique de vapeur dans l'air humide) :
    q = w / (1 + w)
    """
    w = humidity_ratio_w(P_Pa, e_Pa)
    return w / (1.0 + w)


def dew_point_C_from_vapor_pressure_Tetens(e_Pa: float) -> float:
    """
    Inversion approximative de Tetens pour obtenir Td (°C) depuis e (Pa).
    e_hPa = 6.1078 * exp(17.269*Td/(237.3+Td))
    => Td = (237.3 * ln(e/6.1078)) / (17.269 - ln(e/6.1078))

    Source : DewpointCalculations.pdf (même famille d'équations).
    """
    if e_Pa <= 0:
        raise ValueError("e_Pa doit être > 0.")
    e_hPa = e_Pa / 100.0
    ln_arg = log(e_hPa / 6.1078)
    return (237.3 * ln_arg) / (17.269 - ln_arg)


# =========================
# Propriétés thermo / fluide
# =========================

def dynamic_viscosity_air_Pa_s(T_K: float) -> float:
    """
    Viscosité dynamique air (approx) via Sutherland compacte ISA :
    mu = 1.458e-6 * T^(3/2) / (T + 110.4)   [Pa*s]
    """
    if T_K <= 0:
        raise ValueError("T_K doit être > 0.")
    return SUTH_MU_C1 * (T_K ** 1.5) / (T_K + SUTH_MU_S)


def cp_dry_air_J_kgK(gamma: float = GAMMA_DRY, R_spec: float = R_DRY) -> float:
    """
    cp (air sec) cohérent avec gamma et R (approx).
    cp = gamma*R/(gamma-1)
    """
    if gamma <= 1.0:
        raise ValueError("gamma doit être > 1.")
    return gamma * R_spec / (gamma - 1.0)


def cp_moist_air_J_kgK(q: float, cp_dry: float, cp_vapor: float = 1860.0) -> float:
    """
    cp mélange (approx massique) :
    cp = (1-q)*cp_dry + q*cp_vapor
    """
    if not (0.0 <= q < 1.0):
        raise ValueError("q doit être dans [0,1).")
    return (1.0 - q) * cp_dry + q * cp_vapor


def gamma_from_cp_R(cp: float, R_spec: float) -> float:
    """gamma = cp / (cp - R)."""
    if cp <= R_spec:
        raise ValueError("cp doit être > R_spec.")
    return cp / (cp - R_spec)


def speed_of_sound_m_s(T_K: float, gamma: float, R_spec: float) -> float:
    """a = sqrt(gamma * R * T)."""
    if T_K <= 0:
        raise ValueError("T_K doit être > 0.")
    return sqrt(gamma * R_spec * T_K)


def thermal_conductivity_W_mK(mu: float, cp: float, Pr: float = PR_AIR_DEFAULT) -> float:
    """
    Conductivité thermique estimée par relation k = mu * cp / Pr.
    Pr ~ 0.71 pour l'air (ordre de grandeur).
    """
    if mu <= 0 or cp <= 0:
        raise ValueError("mu et cp doivent être > 0.")
    if Pr <= 0:
        raise ValueError("Pr doit être > 0.")
    return mu * cp / Pr


# =========================
# Etat d'air complet
# =========================

@dataclass(frozen=True)
class AirState:
    # Conditions
    altitude_m: float
    T_K: float
    p_Pa: float
    RH: float
    co2_ppm: float

    # Humidité
    e_Pa: float  # pression partielle H2O
    pd_Pa: float  # pression partielle air sec
    w: float  # humidity ratio (kg_vapeur / kg_air_sec)
    q: float  # specific humidity (kg_vapeur / kg_air_humide)
    Td_C: Optional[float]

    # Mélange (gaz)
    M_mix_kg_per_mol: float
    R_spec: float

    # Grandeurs fluides
    rho_kg_m3: float
    mu_Pa_s: float
    nu_m2_s: float
    cp_J_kgK: float
    gamma: float
    a_m_s: float
    k_W_mK: float
    Pr: float

    # Partiels (utile combustion / oxygène disponible)
    pO2_Pa: float
    pN2_Pa: float
    pAr_Pa: float
    pCO2_Pa: float

    # Densités partielles (kg/m3) des constituants secs (approx idéal)
    rho_O2_kg_m3: float
    rho_N2_kg_m3: float

    # Divers
    number_density_1_m3: float  # n = p/(kB*T) (molécules/m³ approx)
    oxygen_mass_fraction: float

    def mach(self, v_m_s: float) -> float:
        """Mach = v/a."""
        if v_m_s < 0:
            raise ValueError("v_m_s doit être >= 0.")
        return v_m_s / self.a_m_s

    def reynolds(self, v_m_s: float, L_m: float) -> float:
        """Re = rho*v*L/mu."""
        if v_m_s < 0:
            raise ValueError("v_m_s doit être >= 0.")
        if L_m <= 0:
            raise ValueError("L_m doit être > 0.")
        return self.rho_kg_m3 * v_m_s * L_m / self.mu_Pa_s

    def dynamic_pressure_Pa(self, v_m_s: float) -> float:
        """q_dyn = 1/2 * rho * v^2."""
        if v_m_s < 0:
            raise ValueError("v_m_s doit être >= 0.")
        return 0.5 * self.rho_kg_m3 * v_m_s * v_m_s


def _partial_pressures_dry_components(pd_Pa: float, co2_ppm: float) -> Dict[str, float]:
    """Répartit la pression partielle air sec pd entre N2/O2/Ar/CO2."""
    y = dry_air_mole_fractions(co2_ppm=co2_ppm)
    return {k: pd_Pa * y[k] for k in ("N2", "O2", "Ar", "CO2")}


def air_state(
    altitude_m: float,
    temperature_offset_K: float = 0.0,
    RH: float = 0.0,
    co2_ppm: float = 420.0,
    use_geopotential: bool = True,
    Pr: float = PR_AIR_DEFAULT,
    use_coolprop_if_available: bool = False,
) -> AirState:
    """
    Calcule un état d'air détaillé (ISA + humidité optionnelle).

    Args:
        altitude_m: altitude géométrique (m)
        temperature_offset_K: delta T ajouté à l'ISA (ex: +15 K si jour chaud)
        RH: humidité relative [0..1]
        co2_ppm: CO2 en ppmv (approx)
        use_geopotential: applique conversion ISA h->H
        Pr: nombre de Prandtl (si on estime k via mu*cp/Pr)
        use_coolprop_if_available: si True, tente CoolProp pour humid air (sinon fallback)
    """
    if not (0.0 <= RH <= 1.0):
        raise ValueError("RH doit être dans [0,1].")

    # 1) ISA air sec
    T_isa, p = isa_dry_temperature_pressure(altitude_m, use_geopotential=use_geopotential)
    T = T_isa + temperature_offset_K
    if T <= 0:
        raise ValueError("Température finale <= 0 K (invalide).")

    # 2) Humidité (si RH>0)
    T_C = T - 273.15
    e = vapor_pressure_from_RH(p, T_C, RH) if RH > 0 else 0.0
    pd = p - e

    w = humidity_ratio_w(p, e) if e > 0 else 0.0
    q = specific_humidity_q(p, e) if e > 0 else 0.0
    Td_C = dew_point_C_from_vapor_pressure_Tetens(e) if e > 0 else None

    # 3) Mélange gaz : M_mix = sum(y_i * M_i), y_i = p_i/p
    # Ici y_H2O = e/p ; y_dry = pd/p avec M_dry basé sur composition N2/O2/Ar/CO2.
    # On calcule M_dry via fractions molaires.
    y_dry = dry_air_mole_fractions(co2_ppm=co2_ppm)
    M_dry_mix = mixture_molar_mass_from_mole_fractions(y_dry)  # kg/mol
    M_mix = (pd / p) * M_dry_mix + (e / p) * M_WV
    R_spec = R_UNIV / M_mix

    # 4) Propriétés thermo/fluide (fallback)
    rho = isa_density(p, T, R_spec=R_spec)
    mu = dynamic_viscosity_air_Pa_s(T)
    nu = mu / rho

    # cp/gamma : approximation massique avec vapeur d'eau
    cp_dry = cp_dry_air_J_kgK(gamma=GAMMA_DRY, R_spec=R_DRY)
    cp_mix = cp_moist_air_J_kgK(q=q, cp_dry=cp_dry, cp_vapor=1860.0)
    gamma_mix = gamma_from_cp_R(cp_mix, R_spec)
    a = speed_of_sound_m_s(T, gamma_mix, R_spec)
    k = thermal_conductivity_W_mK(mu, cp_mix, Pr=Pr)

    # 5) Partiels secs
    pp = _partial_pressures_dry_components(pd, co2_ppm=co2_ppm)
    pO2 = pp["O2"]
    pN2 = pp["N2"]
    pAr = pp["Ar"]
    pCO2 = pp["CO2"]

    # Densités partielles (approx idéal) : rho_i = p_i * M_i / (R_univ * T)
    rho_O2 = pO2 * MOLAR_MASS["O2"] / (R_UNIV * T)
    rho_N2 = pN2 * MOLAR_MASS["N2"] / (R_UNIV * T)

    # Densité moléculaire (approx) : n = p/(kB*T) (molécules/m3)
    n_molecules = p / (K_B * T)

    # Fraction massique d'oxygène dans l'air sec, puis ajustement grossier par humidité :
    # (si q augmente, l'oxygène massique totale diminue).
    Y_O2_dry = oxygen_mass_fraction_in_dry_air(co2_ppm=co2_ppm)
    oxygen_mass_fraction = (1.0 - q) * Y_O2_dry  # approx

    # 6) Option CoolProp (si demandé et disponible)
    # Remarque : on conserve ISA pour p/T ; CoolProp sert à raffiner cp/k/etc si dispo.
    if use_coolprop_if_available:
        try:
            # CoolProp expose HAPropsSI pour air humide.
            # Exemple (SI) : HAPropsSI('H','T',T,'P',p,'R',RH) -> enthalpie J/kg dry air
            from CoolProp.HumidAirProp import HAPropsSI  # type: ignore

            # cp massique (par kg d'air humide) : CoolProp donne souvent par kg dry air ;
            # on évite d'imposer ici un schéma, donc on ne remplace que si c'est cohérent.
            # On récupère cp_ma = cp (J/kg/K) "mixture" si possible via 'C'
            cp_cp = float(HAPropsSI("C", "T", T, "P", p, "R", RH))
            # viscosité dynamique (Pa*s) : 'V' (kg/m/s)
            mu_cp = float(HAPropsSI("V", "T", T, "P", p, "R", RH))
            # conductivité thermique (W/m/K) : 'K'
            k_cp = float(HAPropsSI("K", "T", T, "P", p, "R", RH))
            # densité (kg/m3) : 'D'
            rho_cp = float(HAPropsSI("D", "T", T, "P", p, "R", RH))

            # on remplace si valeurs plausibles
            if cp_cp > 0 and mu_cp > 0 and k_cp > 0 and rho_cp > 0:
                rho = rho_cp
                mu = mu_cp
                nu = mu / rho
                cp_mix = cp_cp
                gamma_mix = gamma_from_cp_R(cp_mix, R_spec)
                a = speed_of_sound_m_s(T, gamma_mix, R_spec)
                k = k_cp
        except Exception:
            pass

    return AirState(
        altitude_m=altitude_m,
        T_K=T,
        p_Pa=p,
        RH=RH,
        co2_ppm=co2_ppm,
        e_Pa=e,
        pd_Pa=pd,
        w=w,
        q=q,
        Td_C=Td_C,
        M_mix_kg_per_mol=M_mix,
        R_spec=R_spec,
        rho_kg_m3=rho,
        mu_Pa_s=mu,
        nu_m2_s=nu,
        cp_J_kgK=cp_mix,
        gamma=gamma_mix,
        a_m_s=a,
        k_W_mK=k,
        Pr=Pr,
        pO2_Pa=pO2,
        pN2_Pa=pN2,
        pAr_Pa=pAr,
        pCO2_Pa=pCO2,
        rho_O2_kg_m3=rho_O2,
        rho_N2_kg_m3=rho_N2,
        number_density_1_m3=n_molecules,
        oxygen_mass_fraction=oxygen_mass_fraction,
    )


# =========================
# Inversions utiles
# =========================

def altitude_from_pressure_ISA(p_target_Pa: float, tol_Pa: float = 0.5) -> float:
    """
    Approximation numérique : trouve altitude (m) telle que p_ISA(alt)=p_target.
    Domaine : 0..85 km (ISA simplifié).
    """
    if p_target_Pa <= 0:
        raise ValueError("p_target_Pa doit être > 0.")
    # bornes
    lo, hi = 0.0, 85_000.0
    p_lo = isa_dry_temperature_pressure(lo)[1]
    p_hi = isa_dry_temperature_pressure(hi)[1]
    if not (p_hi <= p_target_Pa <= p_lo):
        raise ValueError("p_target hors plage ISA (0..85 km).")

    for _ in range(80):
        mid = 0.5 * (lo + hi)
        p_mid = isa_dry_temperature_pressure(mid)[1]
        if abs(p_mid - p_target_Pa) <= tol_Pa:
            return mid
        if p_mid > p_target_Pa:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


__all__ = [
    "AirState",
    "AtmosphereLayer",
    "ISA_LAYERS",
    "air_state",
    "isa_dry_temperature_pressure",
    "altitude_from_pressure_ISA",
    "geometric_to_geopotential",
    "geopotential_to_geometric",
    "saturation_vapor_pressure_Pa_Tetens",
    "vapor_pressure_from_RH",
    "humidity_ratio_w",
    "specific_humidity_q",
    "dew_point_C_from_vapor_pressure_Tetens",
    "dynamic_viscosity_air_Pa_s",
    "thermal_conductivity_W_mK",
    "oxygen_mass_fraction_in_dry_air",
    "dry_air_mole_fractions",
]
