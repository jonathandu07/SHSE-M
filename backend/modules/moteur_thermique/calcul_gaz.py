# backend/modules/moteur_thermique/calcul_gaz.py
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union, TypedDict

Number = Union[int, float]


# =============================================================================
# Validation & utilitaires numériques (uniques, robustes)
# =============================================================================

def _is_finite_number(x: Any) -> bool:
    # bool est un int en Python -> on l'exclut explicitement
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite_number(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_nonneg(name: str, x: Any) -> float:
    v = _req_finite(name, x)
    if v < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


def _req_pos(name: str, x: Any) -> float:
    v = _req_finite(name, x)
    if v <= 0.0:
        raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    return v


def _req_bool(name: str, x: Any) -> bool:
    if isinstance(x, bool):
        return bool(x)
    raise ValueError(f"{name} doit être un booléen (reçu: {x!r}).")


def _pow_pos(base: float, exp: float, *, name_base: str = "base") -> float:
    """
    Puissance robuste pour des relations isentropiques : base doit être > 0 (sinon non physique / NaN).
    """
    if base <= 0.0:
        raise ValueError(f"{name_base} doit être > 0 pour une puissance réelle (reçu: {base}).")
    return base ** exp


def _safe_div(num: float, den: float, *, name_den: str = "denominateur", eps: float = 1e-18) -> float:
    if den == 0.0 or abs(den) <= eps:
        raise ValueError(f"{name_den} trop petit (|{name_den}| <= {eps}).")
    return num / den


# =============================================================================
# Gaz parfait : fonctions directes (sans hypothèse implicite hors entrées)
# =============================================================================

def calcul_pression_gaz_parfait(
    masse_kg: Number,
    volume_m3: Number,
    temperature_k: Number,
    constante_gaz_r: Number = 287.05,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Loi des gaz parfaits (forme massique) :
      P = (m * R * T) / V

    Contraintes physiques :
    - m >= 0
    - V > 0
    - T > 0 (K)
    - R > 0 (J/(kg·K))
    """
    m = _req_nonneg("masse_kg", masse_kg)
    V = _req_pos("volume_m3", volume_m3)
    T = _req_pos("temperature_k", temperature_k)
    R = _req_pos("constante_gaz_r", constante_gaz_r)

    P = (m * R * T) / V

    if not return_details:
        return P

    rho = m / V
    v_spec = V / m if m > 0.0 else float("inf")  # volume spécifique
    return {
        "pression_pa": P,
        "masse_kg": m,
        "volume_m3": V,
        "temperature_k": T,
        "constante_gaz_r": R,
        "densite_kg_m3": rho,
        "volume_specifique_m3_kg": v_spec,
    }


def calcul_masse_gaz_parfait(
    pression_pa: Number,
    volume_m3: Number,
    temperature_k: Number,
    constante_gaz_r: Number = 287.05,
    *,
    allow_zero_pression: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Inversion :
      m = (P * V) / (R * T)

    Contraintes :
    - P >= 0 (pression absolue)
    - V > 0
    - T > 0
    - R > 0
    """
    P = _req_nonneg("pression_pa", pression_pa)
    if (not allow_zero_pression) and P == 0.0:
        raise ValueError("pression_pa ne peut pas être nulle (allow_zero_pression=False).")

    V = _req_pos("volume_m3", volume_m3)
    T = _req_pos("temperature_k", temperature_k)
    R = _req_pos("constante_gaz_r", constante_gaz_r)

    m = (P * V) / (R * T)

    if not return_details:
        return m

    rho = m / V
    return {
        "masse_kg": m,
        "pression_pa": P,
        "volume_m3": V,
        "temperature_k": T,
        "constante_gaz_r": R,
        "densite_kg_m3": rho,
    }


def calcul_temperature_gaz_parfait(
    pression_pa: Number,
    volume_m3: Number,
    masse_kg: Number,
    constante_gaz_r: Number = 287.05,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Inversion :
      T = (P * V) / (m * R)

    Contraintes :
    - P >= 0 (pression absolue)
    - V > 0
    - m > 0 (sinon T indéfinie)
    - R > 0
    """
    P = _req_nonneg("pression_pa", pression_pa)
    V = _req_pos("volume_m3", volume_m3)
    m = _req_pos("masse_kg", masse_kg)
    R = _req_pos("constante_gaz_r", constante_gaz_r)

    T = (P * V) / (m * R)

    if not return_details:
        return T

    rho = m / V
    return {
        "temperature_k": T,
        "pression_pa": P,
        "volume_m3": V,
        "masse_kg": m,
        "constante_gaz_r": R,
        "densite_kg_m3": rho,
    }


def calcul_volume_gaz_parfait(
    pression_pa: Number,
    masse_kg: Number,
    temperature_k: Number,
    constante_gaz_r: Number = 287.05,
    *,
    allow_zero_pression: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Inversion :
      V = (m * R * T) / P

    Contraintes :
    - P > 0 (ou P >= 0 si allow_zero_pression=True, mais alors V -> inf si P=0)
    - m >= 0
    - T > 0
    - R > 0
    """
    P = _req_nonneg("pression_pa", pression_pa)
    if (not allow_zero_pression) and P <= 0.0:
        raise ValueError("pression_pa doit être > 0 (allow_zero_pression=False).")

    m = _req_nonneg("masse_kg", masse_kg)
    T = _req_pos("temperature_k", temperature_k)
    R = _req_pos("constante_gaz_r", constante_gaz_r)

    if P == 0.0:
        V = float("inf") if m > 0.0 else 0.0
    else:
        V = (m * R * T) / P

    if not return_details:
        return V

    rho = (m / V) if (math.isfinite(V) and V > 0.0) else 0.0
    return {
        "volume_m3": V,
        "pression_pa": P,
        "masse_kg": m,
        "temperature_k": T,
        "constante_gaz_r": R,
        "densite_kg_m3": rho,
    }


def calcul_densite_gaz_parfait(
    pression_pa: Number,
    temperature_k: Number,
    constante_gaz_r: Number = 287.05,
    *,
    allow_zero_pression: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Densité d'un gaz parfait :
      rho = P / (R * T)

    Contraintes :
    - P >= 0
    - T > 0
    - R > 0
    """
    P = _req_nonneg("pression_pa", pression_pa)
    if (not allow_zero_pression) and P == 0.0:
        raise ValueError("pression_pa ne peut pas être nulle (allow_zero_pression=False).")
    T = _req_pos("temperature_k", temperature_k)
    R = _req_pos("constante_gaz_r", constante_gaz_r)

    rho = P / (R * T)

    if not return_details:
        return rho

    return {
        "densite_kg_m3": rho,
        "pression_pa": P,
        "temperature_k": T,
        "constante_gaz_r": R,
    }


# =============================================================================
# Isentropique (adiabatique réversible) - relations gaz parfait
# =============================================================================

def calcul_temperature_compression_adiabatique(
    t1_k: Number,
    p1_pa: Number,
    p2_pa: Number,
    gamma: Number = 1.4,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Relation isentropique :
      T2 = T1 * (P2/P1)^((γ - 1)/γ)

    Contraintes :
    - T1 > 0, P1 > 0, P2 > 0
    - γ > 1
    """
    T1 = _req_pos("t1_k", t1_k)
    P1 = _req_pos("p1_pa", p1_pa)
    P2 = _req_pos("p2_pa", p2_pa)
    g = _req_pos("gamma", gamma)
    if g <= 1.0:
        raise ValueError("gamma doit être > 1 pour une transformation isentropique réaliste.")

    rapport_p = P2 / P1
    exposant = (g - 1.0) / g
    T2 = T1 * _pow_pos(rapport_p, exposant, name_base="P2/P1")

    if not return_details:
        return T2

    return {
        "t2_k": T2,
        "t1_k": T1,
        "p1_pa": P1,
        "p2_pa": P2,
        "gamma": g,
        "rapport_p": rapport_p,
        "exposant": exposant,
    }


def calcul_pression_isentropique_depuis_temperature(
    t1_k: Number,
    t2_k: Number,
    p1_pa: Number,
    gamma: Number = 1.4,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Inversion isentropique :
      T2/T1 = (P2/P1)^((γ - 1)/γ)
      => P2 = P1 * (T2/T1)^(γ/(γ - 1))
    """
    T1 = _req_pos("t1_k", t1_k)
    T2 = _req_pos("t2_k", t2_k)
    P1 = _req_pos("p1_pa", p1_pa)
    g = _req_pos("gamma", gamma)
    if g <= 1.0:
        raise ValueError("gamma doit être > 1 pour une transformation isentropique réaliste.")

    ratio_t = T2 / T1
    exp = g / (g - 1.0)
    P2 = P1 * _pow_pos(ratio_t, exp, name_base="T2/T1")

    if not return_details:
        return P2

    return {
        "p2_pa": P2,
        "p1_pa": P1,
        "t1_k": T1,
        "t2_k": T2,
        "gamma": g,
        "ratio_t": ratio_t,
        "exposant": exp,
    }


def calcul_ratio_volume_isentropique_depuis_pression(
    p1_pa: Number,
    p2_pa: Number,
    gamma: Number = 1.4,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Relation isentropique :
      P * V^γ = cste
      => V2/V1 = (P1/P2)^(1/γ)
    """
    P1 = _req_pos("p1_pa", p1_pa)
    P2 = _req_pos("p2_pa", p2_pa)
    g = _req_pos("gamma", gamma)
    if g <= 1.0:
        raise ValueError("gamma doit être > 1.")

    ratio = _pow_pos(P1 / P2, 1.0 / g, name_base="P1/P2")

    if not return_details:
        return ratio

    return {
        "ratio_v2_v1": ratio,
        "p1_pa": P1,
        "p2_pa": P2,
        "gamma": g,
    }


# =============================================================================
# Force gaz sur piston (pression potentiellement signée selon convention)
# =============================================================================

def calcul_force_gaz(
    pression_pa: Number,
    alesage_m: Number,
    *,
    allow_negative_pression: bool = True,
    allow_zero_alesage: bool = False,
    clamp_non_negative: bool = False,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Force exercée par les gaz sur le piston :
      A = π * B² / 4
      F = p * A

    - allow_negative_pression=True : autorise p < 0 (dépression / convention)
    - clamp_non_negative=True : retourne max(0, F)
    """
    p = _req_finite("pression_pa", pression_pa)
    if (not allow_negative_pression) and p < 0.0:
        raise ValueError("pression_pa ne peut pas être négative (allow_negative_pression=False).")

    B = _req_pos("alesage_m", alesage_m) if not allow_zero_alesage else _req_nonneg("alesage_m", alesage_m)
    aire = (math.pi * (B ** 2)) / 4.0
    F = p * aire

    if clamp_non_negative:
        F = max(0.0, F)

    if not return_details:
        return F

    return {
        "force_gaz_n": F,
        "pression_pa": p,
        "alesage_m": B,
        "aire_piston_m2": aire,
    }


# =============================================================================
# Fuites (jeu annulaire, Poiseuille laminaire) + diagnostics calculables
# =============================================================================

def calcul_debit_fuite_annulaire(
    delta_p_pa: Number,
    jeu_radial_h_m: Number,
    rayon_m: Number,
    longueur_fuite_l_m: Number,
    viscosite_dynamique_pa_s: Number,
    *,
    use_abs_delta_p: bool = True,
    epsilon: Number = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Poiseuille (laminaire) dans un jeu annulaire mince (approximation) :
      Q = (π * r * h^3 * ΔP) / (6 * μ * L)

    Remarques :
    - use_abs_delta_p=True : magnitude (Q>=0 si clamp_non_negative=True)
    - use_abs_delta_p=False : conserve le signe de ΔP
    """
    dP = _req_finite("delta_p_pa", delta_p_pa)
    h = _req_nonneg("jeu_radial_h_m", jeu_radial_h_m)
    r = _req_nonneg("rayon_m", rayon_m)
    L = _req_pos("longueur_fuite_l_m", longueur_fuite_l_m)
    mu = _req_pos("viscosite_dynamique_pa_s", viscosite_dynamique_pa_s)
    eps = _req_pos("epsilon", epsilon)

    if L <= eps:
        raise ValueError("longueur_fuite_l_m trop petite (risque de division par ~0).")
    if mu <= eps:
        raise ValueError("viscosite_dynamique_pa_s trop petite (risque de division par ~0).")

    dP_eff = abs(dP) if use_abs_delta_p else dP

    numerateur = math.pi * r * (h ** 3) * dP_eff
    denominateur = 6.0 * mu * L
    Q = numerateur / denominateur

    if use_abs_delta_p and clamp_non_negative:
        Q = max(0.0, Q)

    if not return_details:
        return Q

    # aire de passage approx (jeu annulaire mince) : A ~ 2π r h
    aire_passage = (2.0 * math.pi * r * h) if (r > 0.0 and h > 0.0) else 0.0
    v_moy = (Q / aire_passage) if aire_passage > 0.0 else 0.0
    # diamètre hydraulique approx pour fente annulaire mince : Dh ~ 2h
    dh = 2.0 * h

    return {
        "Q_m3_s": Q,
        "delta_p_pa": float(dP),
        "delta_p_eff_pa": float(dP_eff),
        "jeu_radial_h_m": float(h),
        "rayon_m": float(r),
        "longueur_fuite_l_m": float(L),
        "viscosite_dynamique_pa_s": float(mu),
        "numerateur": float(numerateur),
        "denominateur": float(denominateur),
        "use_abs_delta_p": 1.0 if use_abs_delta_p else 0.0,
        "clamp_non_negative": 1.0 if clamp_non_negative else 0.0,
        "epsilon": float(eps),
        # diagnostics purement géométriques (pas d'hypothèse additionnelle)
        "aire_passage_approx_m2": float(aire_passage),
        "vitesse_moyenne_approx_m_s": float(v_moy),
        "diametre_hydraulique_approx_m": float(dh),
    }


def calcul_masse_fuite(
    debit_volumique_m3s: Number,
    densite_kg_m3: Number,
    *,
    use_abs_debit: bool = True,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Débit massique :
      m_dot = ρ * Q
    """
    Q = _req_finite("debit_volumique_m3s", debit_volumique_m3s)
    rho = _req_nonneg("densite_kg_m3", densite_kg_m3)

    Q_eff = abs(Q) if use_abs_debit else Q
    m_dot = Q_eff * rho

    if use_abs_debit and clamp_non_negative:
        m_dot = max(0.0, m_dot)

    if not return_details:
        return m_dot

    return {
        "m_dot_kg_s": m_dot,
        "debit_volumique_m3s": float(Q),
        "debit_volumique_eff_m3s": float(Q_eff),
        "densite_kg_m3": float(rho),
        "use_abs_debit": 1.0 if use_abs_debit else 0.0,
        "clamp_non_negative": 1.0 if clamp_non_negative else 0.0,
    }


def calcul_reynolds_fuite_annulaire(
    densite_kg_m3: Number,
    debit_volumique_m3s: Number,
    rayon_m: Number,
    jeu_radial_h_m: Number,
    viscosite_dynamique_pa_s: Number,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Reynolds (approx) pour un jeu annulaire mince :
      A ~ 2π r h
      v ~ Q / A
      Dh ~ 2h
      Re = ρ * v * Dh / μ

    Aucun “jugement” de régime n'est imposé : on calcule Re si les entrées existent.
    """
    rho = _req_nonneg("densite_kg_m3", densite_kg_m3)
    Q = _req_finite("debit_volumique_m3s", debit_volumique_m3s)
    r = _req_nonneg("rayon_m", rayon_m)
    h = _req_nonneg("jeu_radial_h_m", jeu_radial_h_m)
    mu = _req_pos("viscosite_dynamique_pa_s", viscosite_dynamique_pa_s)

    aire = (2.0 * math.pi * r * h) if (r > 0.0 and h > 0.0) else 0.0
    v = (Q / aire) if aire > 0.0 else 0.0
    dh = 2.0 * h

    Re = (rho * v * dh) / mu if (mu > 0.0) else float("inf")

    if not return_details:
        return Re

    return {
        "reynolds": float(Re),
        "densite_kg_m3": float(rho),
        "debit_volumique_m3s": float(Q),
        "rayon_m": float(r),
        "jeu_radial_h_m": float(h),
        "viscosite_dynamique_pa_s": float(mu),
        "aire_passage_approx_m2": float(aire),
        "vitesse_moyenne_approx_m_s": float(v),
        "diametre_hydraulique_approx_m": float(dh),
    }


# =============================================================================
# Agrégateur : "calcule tout ce qui est déductible" (sans inventer)
# =============================================================================

class ResultatGaz(TypedDict, total=False):
    # Etat gaz
    pression_pa: float
    masse_kg: float
    volume_m3: float
    temperature_k: float
    constante_gaz_r: float
    densite_kg_m3: float
    volume_specifique_m3_kg: float

    # Isentropique
    t2_k: float
    p2_pa: float
    ratio_v2_v1: float
    gamma: float

    # Piston
    alesage_m: float
    aire_piston_m2: float
    force_gaz_n: float

    # Fuite annulaire
    delta_p_pa: float
    debit_fuite_m3_s: float
    debit_fuite_kg_s: float
    jeu_radial_h_m: float
    rayon_fuite_m: float
    longueur_fuite_m: float
    viscosite_dynamique_pa_s: float
    reynolds: float

    # Diagnostic
    inconnues: str


def calculer_gaz_complet(
    *,
    # Etat gaz (donner ce que tu as ; l'agrégateur déduit le reste si possible)
    pression_pa: Optional[Number] = None,
    masse_kg: Optional[Number] = None,
    volume_m3: Optional[Number] = None,
    temperature_k: Optional[Number] = None,
    constante_gaz_r: Number = 287.05,

    # Isentropique (optionnel)
    t1_k: Optional[Number] = None,
    p1_pa: Optional[Number] = None,
    p2_pa: Optional[Number] = None,
    t2_k: Optional[Number] = None,
    gamma: Number = 1.4,

    # Piston (optionnel)
    alesage_m: Optional[Number] = None,

    # Fuite annulaire (optionnel)
    delta_p_pa: Optional[Number] = None,
    jeu_radial_h_m: Optional[Number] = None,
    rayon_fuite_m: Optional[Number] = None,
    longueur_fuite_m: Optional[Number] = None,
    viscosite_dynamique_pa_s: Optional[Number] = None,
) -> ResultatGaz:
    """
    Agrégateur déterministe :
    - calcule tout ce qui est calculable à partir des entrées
    - n'invente rien : si un calcul manque d'entrées, il est listé dans 'inconnues'
    """
    res: ResultatGaz = {}
    inconnues: List[str] = []

    R = _req_pos("constante_gaz_r", constante_gaz_r)
    res["constante_gaz_r"] = R

    # -------- Etat gaz (P, m, V, T) : si 3 connus => 4e déduit
    P = _req_nonneg("pression_pa", pression_pa) if pression_pa is not None else None
    m = _req_nonneg("masse_kg", masse_kg) if masse_kg is not None else None
    V = _req_pos("volume_m3", volume_m3) if volume_m3 is not None else None
    T = _req_pos("temperature_k", temperature_k) if temperature_k is not None else None

    known = {
        "pression_pa": P is not None,
        "masse_kg": m is not None,
        "volume_m3": V is not None,
        "temperature_k": T is not None,
    }
    nb_known = sum(1 for v in known.values() if v)

    if nb_known >= 3:
        if P is None:
            assert m is not None and V is not None and T is not None
            P = (m * R * T) / V
        elif m is None:
            assert P is not None and V is not None and T is not None
            m = (P * V) / (R * T)
        elif V is None:
            assert P is not None and m is not None and T is not None
            V = (m * R * T) / P if P > 0.0 else (float("inf") if m > 0.0 else 0.0)
        elif T is None:
            assert P is not None and m is not None and V is not None
            if m <= 0.0:
                raise ValueError("Impossible de déduire temperature_k : masse_kg doit être > 0.")
            T = (P * V) / (m * R)

    # Enregistrer ce qu'on a (sans forcer)
    if P is not None:
        res["pression_pa"] = P
    else:
        inconnues.append("pression_pa (manque 3/4 parmi P,m,V,T)")

    if m is not None:
        res["masse_kg"] = m
    else:
        inconnues.append("masse_kg (manque 3/4 parmi P,m,V,T)")

    if V is not None:
        res["volume_m3"] = V
    else:
        inconnues.append("volume_m3 (manque 3/4 parmi P,m,V,T)")

    if T is not None:
        res["temperature_k"] = T
    else:
        inconnues.append("temperature_k (manque 3/4 parmi P,m,V,T)")

    # Densité / volume spécifique si possible
    if (P is not None) and (T is not None):
        rho = P / (R * T)
        res["densite_kg_m3"] = rho
    elif (m is not None) and (V is not None) and (math.isfinite(V)) and (V > 0.0):
        rho = m / V
        res["densite_kg_m3"] = rho
    else:
        inconnues.append("densite_kg_m3 (besoin P&T ou m&V)")

    if (m is not None) and (V is not None):
        res["volume_specifique_m3_kg"] = (V / m) if m > 0.0 else float("inf")

    # -------- Isentropique : calcule T2 si T1,P1,P2 ; ou P2 si T1,T2,P1
    g = _req_pos("gamma", gamma)
    if g <= 1.0:
        raise ValueError("gamma doit être > 1.")
    res["gamma"] = g

    T1i = _req_pos("t1_k", t1_k) if t1_k is not None else None
    P1i = _req_pos("p1_pa", p1_pa) if p1_pa is not None else None
    P2i = _req_pos("p2_pa", p2_pa) if p2_pa is not None else None
    T2i = _req_pos("t2_k", t2_k) if t2_k is not None else None

    if (T2i is None) and (T1i is not None) and (P1i is not None) and (P2i is not None):
        T2i = float(calcul_temperature_compression_adiabatique(T1i, P1i, P2i, g))
    if T2i is not None:
        res["t2_k"] = T2i

    if (P2i is None) and (T1i is not None) and (T2i is not None) and (P1i is not None):
        P2i = float(calcul_pression_isentropique_depuis_temperature(T1i, T2i, P1i, g))
    if P2i is not None:
        res["p2_pa"] = P2i

    if (P1i is not None) and (P2i is not None):
        res["ratio_v2_v1"] = float(calcul_ratio_volume_isentropique_depuis_pression(P1i, P2i, g))

    # Si l'utilisateur n'a rien donné en isentropique, on ne marque pas comme inconnue bloquante
    if (t1_k is not None or p1_pa is not None or p2_pa is not None or t2_k is not None):
        # partiel : on indique ce qui manque pour compléter
        if T1i is None:
            inconnues.append("isentropique: t1_k")
        if P1i is None:
            inconnues.append("isentropique: p1_pa")
        # selon ce qui est demandé, on accepte incomplet ; on ne force pas

    # -------- Piston : force gaz si pression & alésage
    if alesage_m is not None:
        B = _req_pos("alesage_m", alesage_m)
        res["alesage_m"] = B
        aire = (math.pi * (B ** 2)) / 4.0
        res["aire_piston_m2"] = aire
        if P is not None:
            res["force_gaz_n"] = P * aire
        else:
            inconnues.append("force_gaz_n (pression_pa manquante)")
    elif alesage_m is None:
        # pas forcément requis
        pass

    # -------- Fuite annulaire : Q si (ΔP,h,r,L,μ), masse si + rho, Re si + rho
    if any(v is not None for v in [delta_p_pa, jeu_radial_h_m, rayon_fuite_m, longueur_fuite_m, viscosite_dynamique_pa_s]):
        dP = _req_finite("delta_p_pa", delta_p_pa) if delta_p_pa is not None else None
        h = _req_nonneg("jeu_radial_h_m", jeu_radial_h_m) if jeu_radial_h_m is not None else None
        r = _req_nonneg("rayon_fuite_m", rayon_fuite_m) if rayon_fuite_m is not None else None
        L = _req_pos("longueur_fuite_m", longueur_fuite_m) if longueur_fuite_m is not None else None
        mu = _req_pos("viscosite_dynamique_pa_s", viscosite_dynamique_pa_s) if viscosite_dynamique_pa_s is not None else None

        if dP is not None:
            res["delta_p_pa"] = dP
        if h is not None:
            res["jeu_radial_h_m"] = h
        if r is not None:
            res["rayon_fuite_m"] = r
        if L is not None:
            res["longueur_fuite_m"] = L
        if mu is not None:
            res["viscosite_dynamique_pa_s"] = mu

        if (dP is not None) and (h is not None) and (r is not None) and (L is not None) and (mu is not None):
            Q = float(calcul_debit_fuite_annulaire(dP, h, r, L, mu))
            res["debit_fuite_m3_s"] = Q

            # m_dot si densité connue
            rho2 = res.get("densite_kg_m3")
            if rho2 is not None:
                res["debit_fuite_kg_s"] = float(calcul_masse_fuite(Q, rho2))
                res["reynolds"] = float(calcul_reynolds_fuite_annulaire(rho2, Q, r, h, mu))
            else:
                inconnues.append("debit_fuite_kg_s / reynolds (densite_kg_m3 manquante)")
        else:
            inconnues.append("debit_fuite_m3_s (besoin ΔP,h,r,L,μ)")

    res["inconnues"] = "; ".join(inconnues) if inconnues else ""
    return res


__all__ = [
    # Gaz parfait (direct + inverses)
    "calcul_pression_gaz_parfait",
    "calcul_masse_gaz_parfait",
    "calcul_temperature_gaz_parfait",
    "calcul_volume_gaz_parfait",
    "calcul_densite_gaz_parfait",
    # Isentropique
    "calcul_temperature_compression_adiabatique",
    "calcul_pression_isentropique_depuis_temperature",
    "calcul_ratio_volume_isentropique_depuis_pression",
    # Piston
    "calcul_force_gaz",
    # Fuites
    "calcul_debit_fuite_annulaire",
    "calcul_masse_fuite",
    "calcul_reynolds_fuite_annulaire",
    # Agrégateur
    "calculer_gaz_complet",
]
