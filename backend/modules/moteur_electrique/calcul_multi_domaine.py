# backend/modules/moteur_electrique/calcul_multi_domaine.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional


# =============================================================================
# Constantes physiques (standards, pas des “hypothèses véhicule”)
# =============================================================================

G_STD = 9.80665        # m/s²
R_AIR = 287.058        # J/(kg·K) air sec (gaz parfait)


# =============================================================================
# Validation robuste (zéro calcul “silencieux” si entrée invalide)
# =============================================================================

def _is_finite(x: Any) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strict: bool = True) -> float:
    v = _req_finite(name, x)
    ok = v > 0.0 if strict else v >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {v}).")
    return v


def _req_ratio_0_1(name: str, x: Any, *, strict_min: bool = True) -> float:
    v = _req_finite(name, x)
    if strict_min:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    if v > 1.0:
        raise ValueError(f"{name} doit être <= 1.0 (reçu: {v}).")
    return v


def _get_req(params: Dict[str, Any], key: str) -> Any:
    if key not in params:
        raise KeyError(f"Paramètre manquant: {key}")
    return params[key]


# =============================================================================
# Air (optionnel) : densité calculée SI et seulement SI l’utilisateur fournit p,T
# =============================================================================

def calcul_densite_air_sec(pression_pa: float, temperature_c: float) -> float:
    """
    Air sec, gaz parfait:
        rho = p / (R * T)

    Args:
        pression_pa: pression absolue (Pa) > 0
        temperature_c: °C (fini)

    Returns:
        rho (kg/m³)
    """
    p = _req_pos("pression_pa", pression_pa, strict=True)
    t_c = _req_finite("temperature_c", temperature_c)
    t_k = t_c + 273.15
    if t_k <= 0.0:
        raise ValueError(f"temperature_c invalide (T(K) <= 0): {temperature_c}")
    return p / (R_AIR * t_k)


# =============================================================================
# Chaîne d'efficacités : conversions mécaniques/électriques (calcul pur)
# =============================================================================

def puissance_meca_depuis_force_vitesse(force_n: float, vitesse_ms: float) -> float:
    """
    P_meca = F * v
    """
    F = _req_pos("force_n", force_n, strict=False)
    v = _req_pos("vitesse_ms", vitesse_ms, strict=False)
    return F * v


def puissance_meca_avant_propulseur(poussée_ou_traction_n: float, vitesse_ms: float, eta_propulseur: float) -> float:
    """
    Si la force calculée est la force "utile" appliquée au fluide (traînée/poussée),
    la puissance mécanique à fournir à l'hélice/propulseur est :
        P_arbre = (F * v) / eta_propulseur
    """
    eta = _req_ratio_0_1("eta_propulseur", eta_propulseur, strict_min=True)
    p_useful = puissance_meca_depuis_force_vitesse(poussée_ou_traction_n, vitesse_ms)
    if p_useful == 0.0:
        return 0.0
    return p_useful / eta


def puissance_elec_depuis_puissance_meca(puissance_meca_w: float, eta_moteur: float, eta_transmission: float = 1.0) -> float:
    """
    P_elec = P_meca / (eta_moteur * eta_transmission)
    """
    Pm = _req_pos("puissance_meca_w", puissance_meca_w, strict=False)
    eta_m = _req_ratio_0_1("eta_moteur", eta_moteur, strict_min=True)
    eta_t = _req_ratio_0_1("eta_transmission", eta_transmission, strict_min=True)

    if Pm == 0.0:
        return 0.0

    denom = eta_m * eta_t
    if denom <= 0.0:
        raise ValueError("Produit eta_moteur * eta_transmission invalide.")
    return Pm / denom


def courant_depuis_puissance_tension(puissance_elec_w: float, tension_v: float) -> float:
    """
    I = P / V
    """
    P = _req_pos("puissance_elec_w", puissance_elec_w, strict=False)
    V = _req_pos("tension_v", tension_v, strict=True)
    if P == 0.0:
        return 0.0
    return P / V


# =============================================================================
# Modèles multi-domaines (uniquement calculs, coefficients en entrée)
# =============================================================================

def calcul_demande_nautique(
    *,
    vitesse_ms: float,
    surface_mouillee_m2: float,
    cw_coque: float,
    rho_eau_kg_m3: float,
    eta_helice: float,
    eta_moteur: float,
    eta_transmission: float = 1.0,
) -> Dict[str, float]:
    """
    Modèle de traînée quadratique (forme “drag”):
        F = 0.5 * rho * S * Cw * v²

    Puis :
        P_arbre = (F * v) / eta_helice
        P_elec  = P_arbre / (eta_moteur * eta_transmission)

    Notes:
    - rho_eau_kg_m3 DOIT être fourni (eau douce / mer / température / salinité => pas “inventé”).
    - Cw et surface mouillée doivent provenir d’un calcul/mesure/estimation externe.
    """
    v = _req_pos("vitesse_ms", vitesse_ms, strict=False)
    S = _req_pos("surface_mouillee_m2", surface_mouillee_m2, strict=False)
    Cw = _req_pos("cw_coque", cw_coque, strict=False)
    rho = _req_pos("rho_eau_kg_m3", rho_eau_kg_m3, strict=True)
    eta_h = _req_ratio_0_1("eta_helice", eta_helice, strict_min=True)

    force_eau = 0.5 * rho * S * Cw * (v ** 2)
    p_arbre = puissance_meca_avant_propulseur(force_eau, v, eta_h)
    p_elec = puissance_elec_depuis_puissance_meca(p_arbre, eta_moteur, eta_transmission)

    return {
        "force_N": float(force_eau),
        "puissance_meca_W": float(p_arbre),
        "puissance_elec_W": float(p_elec),
        "type": "Nautique",
    }


def calcul_demande_aerien_rho(
    *,
    vitesse_ms: float,
    rho_air_kg_m3: float,
    s_cx_cellule_m2: float,
    eta_helice: float,
    eta_moteur: float,
    eta_transmission: float = 1.0,
) -> Dict[str, float]:
    """
    Modèle de traînée parasitaire:
        F = 0.5 * rho * (S*Cx) * v²   (ici s_cx_cellule_m2 = CdA)

    Puis :
        P_arbre = (F * v) / eta_helice
        P_elec  = P_arbre / (eta_moteur * eta_transmission)

    Notes:
    - rho_air_kg_m3 doit être fourni (ou calculé via pression+température avec calcul_densite_air_sec).
    - Ce modèle ne contient PAS de traînée induite, ni puissance de montée, ni profil hélice avancé.
      (Ce n’est pas “inventé” : c’est explicitement hors modèle.)
    """
    v = _req_pos("vitesse_ms", vitesse_ms, strict=False)
    rho = _req_pos("rho_air_kg_m3", rho_air_kg_m3, strict=True)
    CdA = _req_pos("s_cx_cellule_m2", s_cx_cellule_m2, strict=False)
    eta_h = _req_ratio_0_1("eta_helice", eta_helice, strict_min=True)

    force_drag = 0.5 * rho * CdA * (v ** 2)
    p_arbre = puissance_meca_avant_propulseur(force_drag, v, eta_h)
    p_elec = puissance_elec_depuis_puissance_meca(p_arbre, eta_moteur, eta_transmission)

    return {
        "densite_air": float(rho),
        "force_N": float(force_drag),
        "puissance_meca_W": float(p_arbre),
        "puissance_elec_W": float(p_elec),
        "type": "Aérien",
    }


def calcul_demande_ferroviaire_davis(
    *,
    vitesse_ms: float,
    masse_kg: float,
    acceleration_ms2: float,
    davis_A_N: float,
    davis_B_N_s_m: float,
    davis_C_N_s2_m2: float,
    eta_moteur: float,
    eta_transmission: float,
) -> Dict[str, float]:
    """
    Résistance type Davis (forme générale):
        F_res = A + B*v + C*v²     (v en m/s)
    Inertie:
        F_inertie = m * a

    Puis :
        P_meca = (F_total * v) / eta_transmission
        P_elec = P_meca / eta_moteur

    Notes:
    - A,B,C doivent être fournis (spécifiques au train, à la rame, aux bogies, etc.).
      A,B,C “génériques” seraient une invention, donc on refuse de les créer ici.
    """
    v = _req_pos("vitesse_ms", vitesse_ms, strict=False)
    m = _req_pos("masse_kg", masse_kg, strict=True)
    a = _req_finite("acceleration_ms2", acceleration_ms2)

    A = _req_pos("davis_A_N", davis_A_N, strict=False)
    B = _req_pos("davis_B_N_s_m", davis_B_N_s_m, strict=False)
    C = _req_pos("davis_C_N_s2_m2", davis_C_N_s2_m2, strict=False)

    # F_res >= 0 si A,B,C>=0 et v>=0
    force_res = A + B * v + C * (v ** 2)

    # inertie : peut être négative si décélération (freinage).
    # Sans modèle de récupération (freinage, regen), on refuse a<0 pour rester “calcul pur” sans supposer.
    if a < 0.0:
        raise ValueError("acceleration_ms2 < 0 non supportée sans modèle de freinage/régénération.")
    force_inertie = m * a

    force_tot = force_res + force_inertie

    eta_t = _req_ratio_0_1("eta_transmission", eta_transmission, strict_min=True)
    p_meca = 0.0 if (force_tot == 0.0 or v == 0.0) else (force_tot * v) / eta_t
    p_elec = puissance_elec_depuis_puissance_meca(p_meca, eta_moteur, 1.0)

    return {
        "force_N": float(force_tot),
        "force_resistance_N": float(force_res),
        "force_inertie_N": float(force_inertie),
        "puissance_meca_W": float(p_meca),
        "puissance_elec_W": float(p_elec),
        "type": "Ferroviaire",
    }


# =============================================================================
# Wrapper d'intégration (-> Batterie) : strict sur paramètres requis
# =============================================================================

def generer_rapport_mission(
    domaine: Literal["nautique", "aerien", "ferroviaire"],
    params: Dict[str, Any],
    *,
    tension_systeme_v: float,
) -> Dict[str, Any]:
    """
    Retourne un rapport exploitable pour dimensionnement batterie:
      - puissance_elec_W
      - courant_estime_A (si tension_systeme_v fournie)
      - force_N / puissance mécanique, etc.

    Aucune valeur par défaut “typique” (CdA, rendements, densités, Davis A/B/C).
    Tout ce qui est spécifique au système doit être fourni.
    """
    V = _req_pos("tension_systeme_v", tension_systeme_v, strict=True)

    if domaine == "nautique":
        res = calcul_demande_nautique(
            vitesse_ms=_req_pos("vitesse_ms", _get_req(params, "vitesse_ms"), strict=False),
            surface_mouillee_m2=_req_pos("surface_mouillee_m2", _get_req(params, "surface_mouillee_m2"), strict=False),
            cw_coque=_req_pos("cw_coque", _get_req(params, "cw_coque"), strict=False),
            rho_eau_kg_m3=_req_pos("rho_eau_kg_m3", _get_req(params, "rho_eau_kg_m3"), strict=True),
            eta_helice=_req_ratio_0_1("eta_helice", _get_req(params, "eta_helice"), strict_min=True),
            eta_moteur=_req_ratio_0_1("eta_moteur", _get_req(params, "eta_moteur"), strict_min=True),
            eta_transmission=_req_ratio_0_1("eta_transmission", params.get("eta_transmission", 1.0), strict_min=True),
        )

    elif domaine == "aerien":
        # Deux modes possibles:
        # - rho_air_kg_m3 fourni directement
        # - OU pression_pa + temperature_c pour calculer rho (air sec)
        if "rho_air_kg_m3" in params:
            rho_air = _req_pos("rho_air_kg_m3", _get_req(params, "rho_air_kg_m3"), strict=True)
        else:
            p = _req_pos("pression_pa", _get_req(params, "pression_pa"), strict=True)
            t = _req_finite("temperature_c", _get_req(params, "temperature_c"))
            rho_air = float(calcul_densite_air_sec(p, t))

        res = calcul_demande_aerien_rho(
            vitesse_ms=_req_pos("vitesse_ms", _get_req(params, "vitesse_ms"), strict=False),
            rho_air_kg_m3=rho_air,
            s_cx_cellule_m2=_req_pos("s_cx_cellule_m2", _get_req(params, "s_cx_cellule_m2"), strict=False),
            eta_helice=_req_ratio_0_1("eta_helice", _get_req(params, "eta_helice"), strict_min=True),
            eta_moteur=_req_ratio_0_1("eta_moteur", _get_req(params, "eta_moteur"), strict_min=True),
            eta_transmission=_req_ratio_0_1("eta_transmission", params.get("eta_transmission", 1.0), strict_min=True),
        )

    elif domaine == "ferroviaire":
        res = calcul_demande_ferroviaire_davis(
            vitesse_ms=_req_pos("vitesse_ms", _get_req(params, "vitesse_ms"), strict=False),
            masse_kg=_req_pos("masse_kg", _get_req(params, "masse_kg"), strict=True),
            acceleration_ms2=_req_finite("acceleration_ms2", params.get("acceleration_ms2", 0.0)),
            davis_A_N=_req_pos("davis_A_N", _get_req(params, "davis_A_N"), strict=False),
            davis_B_N_s_m=_req_pos("davis_B_N_s_m", _get_req(params, "davis_B_N_s_m"), strict=False),
            davis_C_N_s2_m2=_req_pos("davis_C_N_s2_m2", _get_req(params, "davis_C_N_s2_m2"), strict=False),
            eta_moteur=_req_ratio_0_1("eta_moteur", _get_req(params, "eta_moteur"), strict_min=True),
            eta_transmission=_req_ratio_0_1("eta_transmission", _get_req(params, "eta_transmission"), strict_min=True),
        )

    else:
        raise ValueError("domaine doit être 'nautique', 'aerien' ou 'ferroviaire'.")

    # Courant BMS
    p_elec = _req_pos("puissance_elec_W", res["puissance_elec_W"], strict=False)
    res["courant_estime_A"] = float(courant_depuis_puissance_tension(p_elec, V))
    res["tension_systeme_V"] = float(V)
    return res


if __name__ == "__main__":
    # Exemple AÉRIEN (sans “valeurs typiques”):
    # On fournit rho_air via pression+température (air sec), CdA, rendements.
    test_params = {
        "vitesse_ms": 15.0,
        "pression_pa": 95400.0,          # EXEMPLE : à fournir/mesurer
        "temperature_c": 5.0,            # EXEMPLE : à fournir/mesurer
        "s_cx_cellule_m2": 0.18,          # CdA : à fournir
        "eta_helice": 0.78,               # à fournir
        "eta_moteur": 0.94,               # à fournir
        "eta_transmission": 0.98,         # à fournir si besoin
    }
    rapport = generer_rapport_mission("aerien", test_params, tension_systeme_v=24.0)
    print(f"--- Rapport Mission {rapport['type']} ---")
    print(f"Puissance Électrique : {rapport['puissance_elec_W']:.2f} W")
    print(f"Courant requis (24V) : {rapport['courant_estime_A']:.2f} A")
