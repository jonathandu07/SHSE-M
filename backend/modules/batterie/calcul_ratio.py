# backend/modules/batterie/calcul_ratio.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import math

import numpy as np

# =============================================================================
# Validation (robuste, sans hypothèses implicites)
# =============================================================================

def _is_finite(x: object) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _req_finite(name: str, x: object) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: object, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_ratio_0_1(name: str, x: object, *, strict_min: bool = True) -> float:
    v = _req_finite(name, x)
    if strict_min and v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    if (not strict_min) and v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    if v > 1.0:
        raise ValueError(f"{name} doit être <= 1.0 (reçu: {v}).")
    return v


def _req_int_pos(name: str, x: object) -> int:
    if not isinstance(x, int) or x <= 0:
        raise ValueError(f"{name} doit être un entier > 0 (reçu: {x!r}).")
    return int(x)


# =============================================================================
# Modèles de données (zéro valeur par défaut “inventée”)
# =============================================================================

@dataclass(frozen=True)
class Carburant:
    """
    Propriétés thermochimiques STRICTES.

    lhv_mj_kg : pouvoir calorifique inférieur (MJ/kg)
    rho_kg_l  : densité (kg/L)
    """
    nom: str
    lhv_mj_kg: float
    rho_kg_l: float


@dataclass(frozen=True)
class Vehicule:
    """
    Paramètres “road-load” (régime stationnaire à vitesse constante).
    """
    masse_vide_kg: float
    crr: float                 # coefficient de résistance au roulement
    cda_m2: float              # CdA (m²) = Cx * S
    g_ms2: float = 9.80665     # accélération standard (constante physique)


@dataclass(frozen=True)
class Environnement:
    """
    Air sec (pas d’humidité) : rho peut être fourni directement,
    ou calculé via pression + température (gaz parfait).
    """
    rho_air_kg_m3: Optional[float] = None
    pression_pa: Optional[float] = None
    temperature_c: Optional[float] = None


@dataclass(frozen=True)
class BatteriePack:
    """
    densite_pack_kwh_kg : densité énergétique au niveau pack (kWh/kg)
    facteur_capacite_froid : facteur multiplicatif (0..1) sur la capacité disponible (mesuré/choisi)
    fenetre_soc_utilisable : fraction (0..1) de la capacité nominale utilisable (ex: 0.8)
    eta_batt_vers_roues : rendement global batterie->roues (0..1), incluant électronique + moteur + transmission

    NOTE:
    - Ici eta_batt_vers_roues représente le rendement "électrique pack -> énergie aux roues".
      Le module électrolyte solide vient ajouter des pertes OHMIQUES supplémentaires côté pack.
    """
    densite_pack_kwh_kg: float
    facteur_capacite_froid: float
    fenetre_soc_utilisable: float
    eta_batt_vers_roues: float


@dataclass(frozen=True)
class Thermique:
    """
    Rendement global carburant->roues (0..1).
    Exemple : moteur * générateur * électronique * moteur traction * transmission,
    OU moteur * transmission si architecture parallèle.
    """
    eta_carburant_vers_roues: float


# =============================================================================
# NOUVEAU : intégration du module électrolyte solide
# =============================================================================

# Import du module que tu as ajouté (même arborescence que ton fichier /mnt/data/electrolyte_solide.py)
from backend.modules.batterie.electrolyte_solide import (
    ElectrolyteSolide,
    CelluleSolide,
    PackSolide,
    Options as OptionsElectrolyte,
    evaluer_electrolyte_solide,
)

# Si ton module calcul_electrique_pack contient déjà ce helper, on l’utilise pour rester homogène.
from backend.modules.batterie.calcul_electrique_pack import calcul_courant_depuis_kw_tension


@dataclass(frozen=True)
class ConfigElectrolyteSolide:
    """
    Configuration minimale pour relier le modèle road-load (ratio)
    aux pertes ohmiques de l’électrolyte solide.

    Aucune valeur par défaut “métier” :
    - si une valeur manque -> elle reste None et la fonction renvoie la liste des inconnues.
    """
    # Électrolyte
    conductivite_ionique_s_m: Optional[float] = None
    epaisseur_m: Optional[float] = None
    resistance_interface_ohm: Optional[float] = None  # optionnel

    # Cellule
    surface_active_m2: Optional[float] = None
    tension_cell_v: Optional[float] = None
    capacite_cell_ah: Optional[float] = None
    courant_cell_max_a: Optional[float] = None  # optionnel

    # Pack
    nb_series: Optional[int] = None
    nb_parallele: Optional[int] = None

    # Si tu veux convertir une puissance "mécanique/roues" en "électrique pack", tu peux donner eta_chaine.
    # Si None : la puissance fournie au modèle électrolyte est supposée déjà être une puissance électrique pack.
    rendement_chaine: Optional[float] = None  # (0,1]


# =============================================================================
# Air : calcul de densité (gaz parfait) — calcul pur
# =============================================================================

def calcul_densite_air_sec(pression_pa: float, temperature_c: float) -> float:
    """
    Air sec (approx gaz parfait):
        rho = p / (R * T)

    R_air ≈ 287.058 J/(kg·K)
    """
    p = _req_pos("pression_pa", pression_pa, strict=True)
    t_c = _req_finite("temperature_c", temperature_c)
    t_k = t_c + 273.15
    if t_k <= 0.0:
        raise ValueError(f"temperature_c invalide (T(K) <= 0): {temperature_c}")
    R_air = 287.058
    return p / (R_air * t_k)


def densite_air(env: Environnement) -> float:
    """
    Déduit rho_air selon les entrées disponibles, sans hypothèse implicite.
    """
    if env.rho_air_kg_m3 is not None:
        return _req_pos("rho_air_kg_m3", env.rho_air_kg_m3, strict=True)

    if env.pression_pa is None or env.temperature_c is None:
        raise ValueError(
            "Environnement: fournir rho_air_kg_m3 OU (pression_pa ET temperature_c)."
        )
    return float(calcul_densite_air_sec(env.pression_pa, env.temperature_c))


# =============================================================================
# Road-load (forces) : calcul pur
# =============================================================================

def calcul_forces_traction(
    *,
    masse_totale_kg: float,
    crr: float,
    pente: float,
    rho_air_kg_m3: float,
    cda_m2: float,
    vitesse_ms: float,
    g_ms2: float = 9.80665,
) -> Dict[str, float]:
    """
    Modèle stationnaire (vitesse constante, pas d’accélération).

    F_roulement = m*g*Crr
    F_pente     = m*g*pente
    F_aero      = 0.5*rho*CdA*v^2

    pente < 0 refusée sans modèle de récupération (regen).
    """
    m = _req_pos("masse_totale_kg", masse_totale_kg, strict=True)
    Crr = _req_pos("crr", crr, strict=False)
    CdA = _req_pos("cda_m2", cda_m2, strict=False)
    rho = _req_pos("rho_air_kg_m3", rho_air_kg_m3, strict=True)
    v = _req_pos("vitesse_ms", vitesse_ms, strict=True)
    g = _req_pos("g_ms2", g_ms2, strict=True)

    pente_v = _req_finite("pente", pente)
    if pente_v < 0.0:
        raise ValueError("pente < 0 non supportée sans modèle de récupération (regen/freinage).")

    f_roulement = m * g * Crr
    f_pente = m * g * pente_v
    f_aero = 0.5 * rho * CdA * (v ** 2)

    f_total = f_roulement + f_pente + f_aero
    return {
        "f_roulement_n": float(f_roulement),
        "f_pente_n": float(f_pente),
        "f_aero_n": float(f_aero),
        "f_total_n": float(f_total),
    }


def energie_roues_sur_distance(
    force_totale_n: float,
    distance_m: float,
) -> Dict[str, float]:
    """
    E = F * d
    """
    F = _req_pos("force_totale_n", force_totale_n, strict=False)
    d = _req_pos("distance_m", distance_m, strict=True)

    e_j = F * d
    e_kwh = e_j / 3.6e6
    return {"energie_j": float(e_j), "energie_kwh": float(e_kwh)}


# =============================================================================
# Conversion carburant : calcul pur
# =============================================================================

def litres_depuis_energie_carburant_kwh(
    energie_carburant_kwh: float,
    carburant: Carburant,
) -> float:
    """
    Convertit une énergie chimique (kWh) en litres, via LHV et densité.

    1 kWh = 3.6 MJ
    masse_carbu (kg) = E(MJ) / LHV(MJ/kg)
    volume (L) = masse (kg) / rho (kg/L)
    """
    e_kwh = _req_pos("energie_carburant_kwh", energie_carburant_kwh, strict=False)
    lhv = _req_pos("carburant.lhv_mj_kg", carburant.lhv_mj_kg, strict=True)
    rho = _req_pos("carburant.rho_kg_l", carburant.rho_kg_l, strict=True)

    if e_kwh == 0.0:
        return 0.0

    e_mj = e_kwh * 3.6
    masse_kg = e_mj / lhv
    volume_l = masse_kg / rho
    return float(volume_l)


# =============================================================================
# Consommation L/100km en fonction de la capacité batterie
# =============================================================================

def conso_l_100km_pour_capacite(
    *,
    capacite_nominale_kwh: float,
    vehicule: Vehicule,
    env: Environnement,
    batterie: BatteriePack,
    thermique: Thermique,
    carburant: Carburant,
    vitesse_kmh: float,
    pente: float,
    distance_km: float = 100.0,
) -> Dict[str, float]:
    """
    Modèle stationnaire:
    - calcule l’énergie aux roues sur distance_km (avec masse batterie).
    - la batterie peut fournir une partie de l’énergie aux roues,
      limitée par son énergie utilisable et le rendement batterie->roues.
    - le reste est fourni par le carburant, via eta_carburant_vers_roues.
    """
    kwh_nom = _req_pos("capacite_nominale_kwh", capacite_nominale_kwh, strict=False)

    dens = _req_pos("batterie.densite_pack_kwh_kg", batterie.densite_pack_kwh_kg, strict=True)
    f_froid = _req_ratio_0_1("batterie.facteur_capacite_froid", batterie.facteur_capacite_froid, strict_min=False)
    f_soc = _req_ratio_0_1("batterie.fenetre_soc_utilisable", batterie.fenetre_soc_utilisable, strict_min=False)
    eta_batt = _req_ratio_0_1("batterie.eta_batt_vers_roues", batterie.eta_batt_vers_roues, strict_min=True)

    eta_fuel = _req_ratio_0_1("thermique.eta_carburant_vers_roues", thermique.eta_carburant_vers_roues, strict_min=True)

    v_ms = _req_pos("vitesse_kmh", vitesse_kmh, strict=True) / 3.6
    d_m = _req_pos("distance_km", distance_km, strict=True) * 1000.0
    rho_air = densite_air(env)

    m_batt = 0.0 if kwh_nom == 0.0 else (kwh_nom / dens)
    m_tot = _req_pos("vehicule.masse_vide_kg", vehicule.masse_vide_kg, strict=True) + m_batt

    forces = calcul_forces_traction(
        masse_totale_kg=m_tot,
        crr=_req_pos("vehicule.crr", vehicule.crr, strict=False),
        pente=pente,
        rho_air_kg_m3=rho_air,
        cda_m2=_req_pos("vehicule.cda_m2", vehicule.cda_m2, strict=False),
        vitesse_ms=v_ms,
        g_ms2=_req_pos("vehicule.g_ms2", vehicule.g_ms2, strict=True),
    )
    e_roues = energie_roues_sur_distance(forces["f_total_n"], d_m)
    e_roues_kwh = float(e_roues["energie_kwh"])

    e_batt_usable_pack_kwh = kwh_nom * f_froid * f_soc
    e_batt_aux_roues_kwh_max = e_batt_usable_pack_kwh * eta_batt

    e_aux_roues_par_batt_kwh = min(e_roues_kwh, e_batt_aux_roues_kwh_max)
    e_aux_roues_par_fuel_kwh = max(0.0, e_roues_kwh - e_aux_roues_par_batt_kwh)

    if e_aux_roues_par_fuel_kwh == 0.0:
        e_carbu_kwh = 0.0
    else:
        e_carbu_kwh = e_aux_roues_par_fuel_kwh / eta_fuel

    litres = litres_depuis_energie_carburant_kwh(e_carbu_kwh, carburant)
    conso_l_100 = litres * (100.0 / distance_km)

    return {
        "capacite_nominale_kwh": float(kwh_nom),
        "masse_batterie_kg": float(m_batt),
        "masse_totale_kg": float(m_tot),
        "rho_air_kg_m3": float(rho_air),
        "energie_roues_kwh_sur_distance": float(e_roues_kwh),
        "energie_batt_usable_pack_kwh": float(e_batt_usable_pack_kwh),
        "energie_batt_roues_kwh": float(e_aux_roues_par_batt_kwh),
        "energie_fuel_roues_kwh": float(e_aux_roues_par_fuel_kwh),
        "energie_carburant_kwh": float(e_carbu_kwh),
        "litres_sur_distance": float(litres),
        "conso_l_100km": float(conso_l_100),
        "forces_n": float(forces["f_total_n"]),
        "f_roulement_n": float(forces["f_roulement_n"]),
        "f_pente_n": float(forces["f_pente_n"]),
        "f_aero_n": float(forces["f_aero_n"]),
    }


def conso_l_100km_pour_capacite_avec_electrolyte_solide(
    *,
    capacite_nominale_kwh: float,
    vehicule: Vehicule,
    env: Environnement,
    batterie: BatteriePack,
    thermique: Thermique,
    carburant: Carburant,
    vitesse_kmh: float,
    pente: float,
    distance_km: float = 100.0,
    ssb: Optional[ConfigElectrolyteSolide] = None,
) -> Dict[str, Any]:
    """
    Variante qui ajoute les pertes ohmiques pack dues à l’électrolyte solide.

    Ce qui est fait (et seulement cela) :
    - on refait le bilan énergétique "comme avant" pour E_roues et le partage batt/fuel.
    - si ssb est fourni ET si la branche batterie fournit >0 kWh aux roues :
        * on estime la puissance moyenne "batterie -> roues" sur la distance
        * on remonte à une puissance électrique pack de base via eta_batt_vers_roues
        * on appelle evaluer_electrolyte_solide() au point continu
        * on convertit pertes_joule_pack_continu_w en kWh sur le temps de trajet
        * on ajoute ces kWh au "kWh pack consommé" (sans changer l'énergie aux roues)

    NOTE : aucune valeur SSB n'est inventée. Si incomplète, tu récupères 'inconnues_electrolyte_solide'.
    """
    # Recalcul "base" (copié/aligné sur conso_l_100km_pour_capacite, pour ne pas dépendre d’un format)
    kwh_nom = _req_pos("capacite_nominale_kwh", capacite_nominale_kwh, strict=False)

    dens = _req_pos("batterie.densite_pack_kwh_kg", batterie.densite_pack_kwh_kg, strict=True)
    f_froid = _req_ratio_0_1("batterie.facteur_capacite_froid", batterie.facteur_capacite_froid, strict_min=False)
    f_soc = _req_ratio_0_1("batterie.fenetre_soc_utilisable", batterie.fenetre_soc_utilisable, strict_min=False)
    eta_batt = _req_ratio_0_1("batterie.eta_batt_vers_roues", batterie.eta_batt_vers_roues, strict_min=True)

    eta_fuel = _req_ratio_0_1("thermique.eta_carburant_vers_roues", thermique.eta_carburant_vers_roues, strict_min=True)

    v_kmh = _req_pos("vitesse_kmh", vitesse_kmh, strict=True)
    v_ms = v_kmh / 3.6
    d_km = _req_pos("distance_km", distance_km, strict=True)
    d_m = d_km * 1000.0
    rho_air = densite_air(env)

    m_batt = 0.0 if kwh_nom == 0.0 else (kwh_nom / dens)
    m_tot = _req_pos("vehicule.masse_vide_kg", vehicule.masse_vide_kg, strict=True) + m_batt

    forces = calcul_forces_traction(
        masse_totale_kg=m_tot,
        crr=_req_pos("vehicule.crr", vehicule.crr, strict=False),
        pente=pente,
        rho_air_kg_m3=rho_air,
        cda_m2=_req_pos("vehicule.cda_m2", vehicule.cda_m2, strict=False),
        vitesse_ms=v_ms,
        g_ms2=_req_pos("vehicule.g_ms2", vehicule.g_ms2, strict=True),
    )
    e_roues = energie_roues_sur_distance(forces["f_total_n"], d_m)
    e_roues_kwh = float(e_roues["energie_kwh"])

    e_batt_usable_pack_kwh = kwh_nom * f_froid * f_soc
    e_batt_aux_roues_kwh_max = e_batt_usable_pack_kwh * eta_batt

    e_aux_roues_par_batt_kwh = min(e_roues_kwh, e_batt_aux_roues_kwh_max)
    e_aux_roues_par_fuel_kwh = max(0.0, e_roues_kwh - e_aux_roues_par_batt_kwh)

    # Branche fuel (identique)
    if e_aux_roues_par_fuel_kwh == 0.0:
        e_carbu_kwh = 0.0
    else:
        e_carbu_kwh = e_aux_roues_par_fuel_kwh / eta_fuel

    litres = litres_depuis_energie_carburant_kwh(e_carbu_kwh, carburant)
    conso_l_100 = litres * (100.0 / d_km)

    # Branche SSB (pertes ohmiques)
    ssb_rapport = None
    inconnues_ssb: Optional[List[str]] = None
    e_pertes_ohmiques_kwh = 0.0

    # kWh pack "de base" pour fournir E_roues_batt
    e_pack_base_kwh = 0.0 if eta_batt == 0.0 else (e_aux_roues_par_batt_kwh / eta_batt)

    if ssb is not None and e_aux_roues_par_batt_kwh > 0.0:
        # Durée du trajet à vitesse constante (h)
        t_h = d_km / v_kmh
        if t_h <= 0.0:
            raise ValueError("Temps de trajet non positif (vitesse_kmh invalide).")

        # Puissance moyenne aux roues
        P_roues_kw = e_roues_kwh / t_h

        # Fraction de la puissance aux roues assurée par la batterie (au niveau roues)
        frac_batt = 0.0 if e_roues_kwh <= 0.0 else (e_aux_roues_par_batt_kwh / e_roues_kwh)
        P_roues_batt_kw = P_roues_kw * frac_batt

        # Puissance électrique pack "de base" (avant pertes ohmiques SSB)
        P_pack_base_kw = P_roues_batt_kw / eta_batt

        elec = ElectrolyteSolide(
            conductivite_ionique_s_m=ssb.conductivite_ionique_s_m,
            epaisseur_m=ssb.epaisseur_m,
            resistance_interface_ohm=ssb.resistance_interface_ohm,
        )
        cell = CelluleSolide(
            surface_active_m2=ssb.surface_active_m2,
            tension_nominale_v=ssb.tension_cell_v,
            capacite_ah=ssb.capacite_cell_ah,
            courant_max_a=ssb.courant_cell_max_a,
        )
        pack_ssb = PackSolide(
            nb_series=ssb.nb_series,
            nb_parallele=ssb.nb_parallele,
            puissance_continue_kw=P_pack_base_kw,
            puissance_pic_kw=None,
            rendement_chaine=ssb.rendement_chaine,
        )

        ssb_rapport = evaluer_electrolyte_solide(elec, cell, pack_ssb, OptionsElectrolyte(strict=False))
        inconnues_ssb = ssb_rapport.inconnues

        if ssb_rapport.pertes_joule_pack_continu_w is not None:
            e_pertes_ohmiques_kwh = float(ssb_rapport.pertes_joule_pack_continu_w) * t_h / 1000.0

    e_pack_total_kwh = e_pack_base_kwh + e_pertes_ohmiques_kwh

    # Courants pack moyens (optionnel, déductible si tu fournis Ns*Vcell => tension_pack_v dans ssb_rapport)
    i_pack_moy_a = None
    if ssb_rapport is not None and ssb_rapport.tension_pack_v is not None:
        Vpack = float(ssb_rapport.tension_pack_v)
        if Vpack > 0.0:
            # puissance moyenne électrique pack consommée (base + pertes) ≈ E_pack_total / t_h
            # mais t_h n'est pas défini si ssb=None ou si pas de pertes; on le recalcule seulement si utile:
            t_h2 = d_km / v_kmh
            P_pack_moy_kw = (e_pack_total_kwh / t_h2) if t_h2 > 0 else 0.0
            i_pack_moy_a = float(calcul_courant_depuis_kw_tension(P_pack_moy_kw, Vpack))

    return {
        # --- sorties base ---
        "capacite_nominale_kwh": float(kwh_nom),
        "masse_batterie_kg": float(m_batt),
        "masse_totale_kg": float(m_tot),
        "rho_air_kg_m3": float(rho_air),
        "energie_roues_kwh_sur_distance": float(e_roues_kwh),
        "energie_batt_usable_pack_kwh": float(e_batt_usable_pack_kwh),
        "energie_batt_roues_kwh": float(e_aux_roues_par_batt_kwh),
        "energie_fuel_roues_kwh": float(e_aux_roues_par_fuel_kwh),
        "energie_carburant_kwh": float(e_carbu_kwh),
        "litres_sur_distance": float(litres),
        "conso_l_100km": float(conso_l_100),
        "forces_n": float(forces["f_total_n"]),
        "f_roulement_n": float(forces["f_roulement_n"]),
        "f_pente_n": float(forces["f_pente_n"]),
        "f_aero_n": float(forces["f_aero_n"]),

        # --- sorties pack batt (consommation réelle côté pack) ---
        "energie_batt_pack_kwh_base": float(e_pack_base_kwh),
        "energie_batt_pack_kwh_pertes_ohmiques": float(e_pertes_ohmiques_kwh),
        "energie_batt_pack_kwh_totale": float(e_pack_total_kwh),

        # --- sorties SSB ---
        "ssb_actif": bool(ssb is not None),
        "rapport_electrolyte_solide": ssb_rapport,
        "inconnues_electrolyte_solide": inconnues_ssb,
        "courant_pack_moyen_a": i_pack_moy_a,
    }


def balayage_capacites(
    *,
    capacites_kwh: np.ndarray,
    vehicule: Vehicule,
    env: Environnement,
    batterie: BatteriePack,
    thermique: Thermique,
    carburants: List[Carburant],
    vitesse_kmh: float,
    pente: float,
    distance_km: float = 100.0,
) -> Dict[str, object]:
    """
    Balaye un vecteur de capacités (kWh) et calcule:
    - conso L/100km pour chaque carburant
    - pire cas (max) carburant pour chaque capacité
    - capacité minimisant le pire cas (minimax)
    """
    if not isinstance(capacites_kwh, np.ndarray):
        raise TypeError("capacites_kwh doit être un np.ndarray.")
    if capacites_kwh.ndim != 1 or capacites_kwh.size == 0:
        raise ValueError("capacites_kwh doit être un vecteur 1D non vide.")
    if len(carburants) == 0:
        raise ValueError("carburants doit contenir au moins 1 carburant.")

    n = int(capacites_kwh.size)
    m = int(len(carburants))
    conso = np.empty((n, m), dtype=float)

    for j, carb in enumerate(carburants):
        for i in range(n):
            res = conso_l_100km_pour_capacite(
                capacite_nominale_kwh=float(capacites_kwh[i]),
                vehicule=vehicule,
                env=env,
                batterie=batterie,
                thermique=thermique,
                carburant=carb,
                vitesse_kmh=vitesse_kmh,
                pente=pente,
                distance_km=distance_km,
            )
            conso[i, j] = float(res["conso_l_100km"])

    pire_cas = np.max(conso, axis=1)
    idx_best = int(np.argmin(pire_cas))
    best_kwh = float(capacites_kwh[idx_best])

    j_worst_at_best = int(np.argmax(conso[idx_best, :]))
    carb_worst = carburants[j_worst_at_best]

    detail_best = conso_l_100km_pour_capacite(
        capacite_nominale_kwh=best_kwh,
        vehicule=vehicule,
        env=env,
        batterie=batterie,
        thermique=thermique,
        carburant=carb_worst,
        vitesse_kmh=vitesse_kmh,
        pente=pente,
        distance_km=distance_km,
    )

    return {
        "capacites_kwh": capacites_kwh,
        "carburants": [c.nom for c in carburants],
        "conso_l_100km_par_carburant": conso,   # shape (n, m)
        "pire_cas_l_100km": pire_cas,           # shape (n,)
        "best_kwh_minimax": best_kwh,
        "best_idx": idx_best,
        "worst_fuel_at_best": carb_worst.nom,
        "detail_best_worst_fuel": detail_best,
        "distance_km": float(distance_km),
        "vitesse_kmh": float(vitesse_kmh),
        "pente": float(pente),
    }
