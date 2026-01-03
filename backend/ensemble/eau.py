# backend/ensemble/eau.py
# Ensemble "Eau" : eau pure, eau salée (eau de mer), mélanges eau+glycol (antigel)
#
# Objectif : fournir un maximum de propriétés thermophysiques utiles aux calculs
# (thermique, hydraulique, RDM couplée fluide/thermique via échanges, pertes de charge, etc.)
#
# Backends (optionnels) recommandés :
# - CoolProp (très pratique, eau + solutions incompressibles type "INCOMP::MITSW[0.035]" / glycols)
#   Docs : https://coolprop.org/fluid_properties/Incompressibles.html
#          https://coolprop.org/fluid_properties/IF97.html
# - iapws (tables eau/vapeur IAPWS-IF97 + transport)
#   Docs : https://iapws.readthedocs.io/en/latest/iapws.iapws97.html
# - gsw (TEOS-10) pour eau de mer (densité, cp, vitesse du son, alpha/beta, etc.)
#   Docs : https://teos-10.github.io/GSW-Python/
#          https://www.teos-10.org/pubs/gsw/html/gsw_rho_t_exact.html
#
# Notes importantes :
# - Les fonctions "gsw" utilisent une pression "sea pressure" en dbar = (P_abs[dbar] - 10.1325 dbar).
# - Les solutions CoolProp INCOMP ont un jeu de sorties limité (T,P,D,C,U,H,S,V,L,Tmin,Tmax).
# - Si aucun backend n'est dispo, ce module refusera les états "eau salée" / "antigel" (pas de corrélations
#   bricolées sans source primaire).
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional
import math


# =========================
# Constantes générales
# =========================
G0 = 9.80665  # m/s²
P_ATM_STD = 101_325.0  # Pa (atmosphère standard)
DBAR_TO_PA = 1.0e4  # Pa
PA_TO_DBAR = 1.0e-4  # dbar/Pa

# Chimie eau (valeurs usuelles)
MOLAR_MASS_H2O_KG_MOL = 18.01528e-3  # kg/mol


# =========================
# Exceptions
# =========================
class EauBackendError(RuntimeError):
    pass


class EauDomaineError(ValueError):
    pass


# =========================
# Détection backends
# =========================
@dataclass(frozen=True)
class BackendsEau:
    coolprop: bool
    iapws: bool
    gsw: bool


def backends_disponibles() -> BackendsEau:
    return BackendsEau(
        coolprop=_has_module("CoolProp.CoolProp"),
        iapws=_has_module("iapws.iapws97"),
        gsw=_has_module("gsw"),
    )


def _has_module(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


# =========================
# Modèle d'état fluide
# =========================
@dataclass(frozen=True)
class EtatFluide:
    # Conditions
    T_K: float
    p_Pa: float
    nom: str

    # Propriétés principales
    rho_kg_m3: float               # densité
    cp_J_kg_K: float               # chaleur massique (isobare)
    mu_Pa_s: float                 # viscosité dynamique
    k_W_m_K: float                 # conductivité thermique

    # Dérivées / utiles
    nu_m2_s: float                 # viscosité cinématique = mu/rho
    Pr: float                      # Prandtl = cp*mu/k
    alpha_th_m2_s: float           # diffusivité thermique = k/(rho*cp)

    # Thermo additionnel (optionnel si dispo)
    cv_J_kg_K: Optional[float] = None
    gamma: Optional[float] = None
    a_son_m_s: Optional[float] = None  # vitesse du son
    sigma_N_m: Optional[float] = None  # tension superficielle
    kappa_s_1_Pa: Optional[float] = None  # compressibilité isentropique ~ 1/(rho*a^2)
    K_s_Pa: Optional[float] = None        # module volumique isentropique ~ rho*a^2

    # Métadonnées
    backend: str = "auto"
    details: Dict[str, Any] = None


def _etat_finalize(
    *,
    T_K: float,
    p_Pa: float,
    nom: str,
    rho: float,
    cp: float,
    mu: float,
    k: float,
    cv: Optional[float],
    a: Optional[float],
    sigma: Optional[float],
    backend: str,
    details: Optional[Dict[str, Any]] = None,
) -> EtatFluide:
    if rho <= 0 or cp <= 0 or mu <= 0 or k <= 0:
        raise EauBackendError(
            f"Propriétés non physiques retournées (rho={rho}, cp={cp}, mu={mu}, k={k}) pour {nom}."
        )
    nu = mu / rho
    Pr = (cp * mu) / k
    alpha_th = k / (rho * cp)

    gamma = None
    if cv is not None and cv > 0:
        gamma = cp / cv

    K_s = None
    kappa_s = None
    if a is not None and a > 0:
        K_s = rho * a * a
        kappa_s = 1.0 / K_s

    return EtatFluide(
        T_K=T_K,
        p_Pa=p_Pa,
        nom=nom,
        rho_kg_m3=rho,
        cp_J_kg_K=cp,
        mu_Pa_s=mu,
        k_W_m_K=k,
        nu_m2_s=nu,
        Pr=Pr,
        alpha_th_m2_s=alpha_th,
        cv_J_kg_K=cv,
        gamma=gamma,
        a_son_m_s=a,
        sigma_N_m=sigma,
        kappa_s_1_Pa=kappa_s,
        K_s_Pa=K_s,
        backend=backend,
        details=details or {},
    )


# =========================
# Helpers thermo/hydraulique
# =========================
def pression_hydrostatique(
    profondeur_m: float,
    rho_kg_m3: float,
    p_surface_Pa: float = P_ATM_STD,
    g_m_s2: float = G0,
) -> float:
    if profondeur_m < 0:
        raise ValueError("profondeur_m doit être >= 0")
    if rho_kg_m3 <= 0:
        raise ValueError("rho_kg_m3 doit être > 0")
    return p_surface_Pa + rho_kg_m3 * g_m_s2 * profondeur_m


def profondeur_depuis_pression(
    p_abs_Pa: float,
    rho_kg_m3: float,
    p_surface_Pa: float = P_ATM_STD,
    g_m_s2: float = G0,
) -> float:
    if rho_kg_m3 <= 0:
        raise ValueError("rho_kg_m3 doit être > 0")
    if p_abs_Pa < p_surface_Pa:
        raise ValueError("p_abs_Pa doit être >= p_surface_Pa")
    return (p_abs_Pa - p_surface_Pa) / (rho_kg_m3 * g_m_s2)


def reynolds(rho_kg_m3: float, v_m_s: float, L_m: float, mu_Pa_s: float) -> float:
    if rho_kg_m3 <= 0 or L_m <= 0 or mu_Pa_s <= 0:
        raise ValueError("rho, L, mu doivent être > 0")
    return rho_kg_m3 * v_m_s * L_m / mu_Pa_s


# =========================
# Backend CoolProp
# =========================
def _coolprop_props_si(out: str, T_K: float, p_Pa: float, fluid: str) -> float:
    from CoolProp.CoolProp import PropsSI  # type: ignore
    return float(PropsSI(out, "T", float(T_K), "P", float(p_Pa), fluid))


def _coolprop_try_many(out_keys: list[str], T_K: float, p_Pa: float, fluid: str) -> Optional[float]:
    for k in out_keys:
        try:
            val = _coolprop_props_si(k, T_K, p_Pa, fluid)
            if math.isfinite(val):
                return float(val)
        except Exception:
            continue
    return None


def _etat_eau_pure_coolprop(T_K: float, p_Pa: float) -> EtatFluide:
    # Essai backend IF97 (souvent robuste/rapide pour eau), puis HEOS.
    fluids = ["IF97::Water", "Water"]
    last_err = None
    for fluid in fluids:
        try:
            rho = _coolprop_props_si("D", T_K, p_Pa, fluid)
            cp = _coolprop_props_si("C", T_K, p_Pa, fluid)
            mu = _coolprop_props_si("V", T_K, p_Pa, fluid)
            k = _coolprop_props_si("L", T_K, p_Pa, fluid)

            cv = _coolprop_try_many(["Cvmass", "CVMASS"], T_K, p_Pa, fluid)
            a = _coolprop_try_many(["A"], T_K, p_Pa, fluid)
            sigma = _coolprop_try_many(["I"], T_K, p_Pa, fluid)  # IF97 doc: I = surface tension

            details = {"fluid": fluid}
            return _etat_finalize(
                T_K=T_K,
                p_Pa=p_Pa,
                nom="Eau pure",
                rho=rho,
                cp=cp,
                mu=mu,
                k=k,
                cv=cv,
                a=a,
                sigma=sigma,
                backend=f"CoolProp({fluid})",
                details=details,
            )
        except Exception as e:
            last_err = e
            continue
    raise EauBackendError(f"CoolProp n'a pas pu calculer l'eau pure: {last_err!r}")


def _etat_incomp_coolprop(T_K: float, p_Pa: float, incomp_name: str) -> EtatFluide:
    # Incompressibles : sorties limitées (D,C,V,L, etc.)
    rho = _coolprop_props_si("D", T_K, p_Pa, incomp_name)
    cp = _coolprop_props_si("C", T_K, p_Pa, incomp_name)
    mu = _coolprop_props_si("V", T_K, p_Pa, incomp_name)
    k = _coolprop_props_si("L", T_K, p_Pa, incomp_name)
    Tmin = _coolprop_try_many(["Tmin"], T_K, p_Pa, incomp_name)
    Tmax = _coolprop_try_many(["Tmax"], T_K, p_Pa, incomp_name)
    details = {"fluid": incomp_name, "Tmin": Tmin, "Tmax": Tmax}
    return _etat_finalize(
        T_K=T_K,
        p_Pa=p_Pa,
        nom=incomp_name,
        rho=rho,
        cp=cp,
        mu=mu,
        k=k,
        cv=None,
        a=None,
        sigma=None,
        backend=f"CoolProp({incomp_name})",
        details=details,
    )


# =========================
# Backend iapws (IAPWS-IF97)
# =========================
def _etat_eau_pure_iapws(T_K: float, p_Pa: float) -> EtatFluide:
    # iapws97 attend la pression en MPa
    from iapws.iapws97 import IAPWS97  # type: ignore

    P_MPa = float(p_Pa) * 1e-6
    st = IAPWS97(T=float(T_K), P=P_MPa)

    # iapws renvoie rho en kg/m³, cp/cv en kJ/kg/K, mu en Pa.s, k en W/m/K, w en m/s, sigma en N/m
    rho = float(st.rho)
    cp = float(st.cp) * 1000.0
    cv = float(st.cv) * 1000.0
    mu = float(st.mu)
    k = float(st.k)
    a = float(getattr(st, "w", float("nan")))
    if not math.isfinite(a):
        a = None
    sigma = float(getattr(st, "sigma", float("nan")))
    if not math.isfinite(sigma):
        sigma = None

    details = {"iapws_region": getattr(st, "region", None)}
    return _etat_finalize(
        T_K=T_K,
        p_Pa=p_Pa,
        nom="Eau pure",
        rho=rho,
        cp=cp,
        mu=mu,
        k=k,
        cv=cv,
        a=a,
        sigma=sigma,
        backend="iapws(IAPWS97)",
        details=details,
    )


# =========================
# Backend gsw (TEOS-10) pour eau de mer
# =========================
def _etat_eau_salee_gsw(T_K: float, p_Pa: float, salinite_g_kg: float) -> EtatFluide:
    import gsw  # type: ignore

    if salinite_g_kg < 0 or salinite_g_kg > 60:
        # TEOS-10 est souvent utilisé avec SA ~ [0..42] g/kg (plage "usuelle"),
        # mais on laisse un peu de marge tout en restant prudent.
        raise EauDomaineError("salinite_g_kg hors plage plausible (0..60 g/kg).")

    t_C = T_K - 273.15
    # sea pressure (dbar) = P_abs(dbar) - 10.1325 dbar
    p_dbar_sea = (p_Pa * PA_TO_DBAR) - (P_ATM_STD * PA_TO_DBAR)
    # En usage océanographique, p_dbar_sea=0 à la surface.
    if p_dbar_sea < 0:
        p_dbar_sea = 0.0

    SA = float(salinite_g_kg)  # g/kg (approx : on prend SA directement)
    rho = float(gsw.rho_t_exact(SA, t_C, p_dbar_sea))
    cp = float(gsw.cp_t_exact(SA, t_C, p_dbar_sea))
    a = float(gsw.sound_speed_t_exact(SA, t_C, p_dbar_sea))

    # TEOS-10 donne aussi alpha/beta exact en fonction de (SA,t,p)
    alpha = float(gsw.alpha_wrt_t_exact(SA, t_C, p_dbar_sea))  # 1/K
    beta = float(gsw.beta_const_t_exact(SA, t_C, p_dbar_sea))   # kg/g

    # gsw ne fournit pas directement mu/k (transport). Pour éviter d'inventer :
    # - si CoolProp est dispo, on complète mu/k via INCOMP::MITSW[x]
    # - sinon on lève une erreur (mu/k nécessaires à pertes de charge / Prandtl).
    if _has_module("CoolProp.CoolProp"):
        # CoolProp : MIT seawater en solution aqueuse, ex. 3.5% => "INCOMP::MITSW[0.035]"
        # Ici salinite_g_kg / 1000 = fraction massique.
        x = salinite_g_kg / 1000.0
        incomp = f"INCOMP::MITSW[{x:.6f}]"
        et_incomp = _etat_incomp_coolprop(T_K, p_Pa, incomp)
        mu = et_incomp.mu_Pa_s
        k = et_incomp.k_W_m_K
        cp2 = et_incomp.cp_J_kg_K  # cp côté CoolProp (pour cohérence Prandtl)
        # On garde rho/cp/a TEOS-10 comme référence "eau de mer" thermo exacte,
        # mais on utilise mu/k/cp (prandtl) de CoolProp pour le transport.
        details = {
            "SA_g_kg": SA,
            "t_C": t_C,
            "p_dbar_sea": p_dbar_sea,
            "alpha_1_K": alpha,
            "beta_kg_g": beta,
            "transport_backend": et_incomp.backend,
            "transport_fluid": et_incomp.details.get("fluid"),
        }
        return _etat_finalize(
            T_K=T_K,
            p_Pa=p_Pa,
            nom="Eau salée (type eau de mer)",
            rho=rho,
            cp=cp2,
            mu=mu,
            k=k,
            cv=None,
            a=a,
            sigma=None,
            backend="gsw(TEOS-10)+CoolProp(INCOMP transport)",
            details=details,
        )

    raise EauBackendError(
        "gsw (TEOS-10) a fourni rho/cp/a/alpha/beta, mais il manque mu/k. "
        "Installe CoolProp pour compléter le transport (INCOMP::MITSW[...])."
    )


# =========================
# API publique
# =========================
BackendMode = Literal["auto", "coolprop", "iapws", "gsw"]


def etat_eau_pure(T_K: float, p_Pa: float, backend: BackendMode = "auto") -> EtatFluide:
    """
    État de l'eau pure (liquide/vapeur selon T,p).
    Renvoie un maximum de propriétés si le backend le permet (vitesse du son, tension superficielle, cv...).
    """
    _check_tp(T_K, p_Pa)

    b = backends_disponibles()
    if backend in ("coolprop", "auto") and b.coolprop:
        return _etat_eau_pure_coolprop(T_K, p_Pa)
    if backend in ("iapws", "auto") and b.iapws:
        return _etat_eau_pure_iapws(T_K, p_Pa)

    raise EauBackendError(
        "Aucun backend dispo pour l'eau pure. "
        "Installe CoolProp (recommandé) ou iapws.\n"
        "  pip install CoolProp\n"
        "  pip install iapws"
    )


def etat_eau_salee(
    T_K: float,
    p_Pa: float,
    salinite_g_kg: float = 35.0,
    backend: BackendMode = "auto",
) -> EtatFluide:
    """
    État eau salée (ciblé eau de mer).
    - backend 'gsw' (TEOS-10) recommandé pour rho/cp/a/alpha/beta exact.
    - mu/k complétés via CoolProp INCOMP::MITSW[x] si dispo (sinon erreur).
    """
    _check_tp(T_K, p_Pa)
    if salinite_g_kg < 0:
        raise ValueError("salinite_g_kg doit être >= 0")

    b = backends_disponibles()
    if backend in ("gsw", "auto") and b.gsw:
        return _etat_eau_salee_gsw(T_K, p_Pa, salinite_g_kg)

    if backend in ("coolprop", "auto") and b.coolprop:
        x = salinite_g_kg / 1000.0
        incomp = f"INCOMP::MITSW[{x:.6f}]"
        et = _etat_incomp_coolprop(T_K, p_Pa, incomp)
        # CoolProp INCOMP ne donne pas alpha/beta TEOS-10, mais donne mu/k/cp/rho.
        et2 = _etat_finalize(
            T_K=T_K,
            p_Pa=p_Pa,
            nom="Eau salée (CoolProp INCOMP::MITSW)",
            rho=et.rho_kg_m3,
            cp=et.cp_J_kg_K,
            mu=et.mu_Pa_s,
            k=et.k_W_m_K,
            cv=None,
            a=None,
            sigma=None,
            backend=et.backend,
            details=et.details,
        )
        return et2

    raise EauBackendError(
        "Aucun backend dispo pour l'eau salée. Installe gsw (+ CoolProp) ou CoolProp seul.\n"
        "  pip install gsw CoolProp"
    )


def etat_antigel(
    T_K: float,
    p_Pa: float,
    fraction_massique_glycol: float,
    type_glycol: Literal["MEG", "MPG"] = "MEG",
    backend: BackendMode = "auto",
) -> EtatFluide:
    """
    Mélange eau + glycol (antigel), basé sur CoolProp INCOMP.
    - MEG : ethylene glycol (aqueous)
    - MPG : propylene glycol (aqueous)
    fraction_massique_glycol : 0.0 -> 1.0 (fraction massique du soluté glycol)
    """
    _check_tp(T_K, p_Pa)
    if not (0.0 <= fraction_massique_glycol <= 1.0):
        raise ValueError("fraction_massique_glycol doit être dans [0,1].")

    b = backends_disponibles()
    if backend in ("coolprop", "auto") and b.coolprop:
        # CoolProp incompressible : concentration du soluté dans l'eau.
        # Ex: 30% massique -> INCOMP::MEG[0.30]
        incomp = f"INCOMP::{type_glycol}[{fraction_massique_glycol:.6f}]"
        et = _etat_incomp_coolprop(T_K, p_Pa, incomp)
        return _etat_finalize(
            T_K=T_K,
            p_Pa=p_Pa,
            nom=f"Antigel eau+{type_glycol} (x={fraction_massique_glycol:.3f})",
            rho=et.rho_kg_m3,
            cp=et.cp_J_kg_K,
            mu=et.mu_Pa_s,
            k=et.k_W_m_K,
            cv=None,
            a=None,
            sigma=None,
            backend=et.backend,
            details=et.details,
        )

    raise EauBackendError(
        "Le calcul antigel nécessite CoolProp (backend INCOMP).\n"
        "  pip install CoolProp"
    )


def temperature_saturation_eau(p_Pa: float, backend: BackendMode = "auto") -> float:
    """
    Température de saturation (liquide, Q=0) de l'eau à une pression donnée.
    Requiert CoolProp ou iapws.
    """
    if p_Pa <= 0:
        raise ValueError("p_Pa doit être > 0")

    b = backends_disponibles()
    if backend in ("coolprop", "auto") and b.coolprop:
        from CoolProp.CoolProp import PropsSI  # type: ignore
        # Exemple CoolProp doc: PropsSI('T','P',101325,'Q',0,'Water')
        return float(PropsSI("T", "P", float(p_Pa), "Q", 0, "Water"))

    if backend in ("iapws", "auto") and b.iapws:
        from iapws.iapws97 import IAPWS97  # type: ignore
        P_MPa = float(p_Pa) * 1e-6
        st = IAPWS97(P=P_MPa, x=0)  # saturated liquid
        return float(st.T)

    raise EauBackendError("Température de saturation nécessite CoolProp ou iapws.")


def pression_saturation_eau(T_K: float, backend: BackendMode = "auto") -> float:
    """
    Pression de saturation de l'eau à une température donnée (liquide, Q=0).
    Requiert CoolProp ou iapws.
    """
    if T_K <= 0:
        raise ValueError("T_K doit être > 0")

    b = backends_disponibles()
    if backend in ("coolprop", "auto") and b.coolprop:
        from CoolProp.CoolProp import PropsSI  # type: ignore
        return float(PropsSI("P", "T", float(T_K), "Q", 0, "Water"))

    if backend in ("iapws", "auto") and b.iapws:
        from iapws.iapws97 import IAPWS97  # type: ignore
        st = IAPWS97(T=float(T_K), x=0)
        return float(st.P) * 1e6  # MPa -> Pa

    raise EauBackendError("Pression de saturation nécessite CoolProp ou iapws.")


# =========================
# Validation de domaine
# =========================
def _check_tp(T_K: float, p_Pa: float) -> None:
    if not (isinstance(T_K, (int, float)) and math.isfinite(T_K)):
        raise ValueError("T_K invalide.")
    if not (isinstance(p_Pa, (int, float)) and math.isfinite(p_Pa)):
        raise ValueError("p_Pa invalide.")
    if T_K <= 0:
        raise EauDomaineError("T_K doit être > 0 K.")
    if p_Pa <= 0:
        raise EauDomaineError("p_Pa doit être > 0 Pa.")
