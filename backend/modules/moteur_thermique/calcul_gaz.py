# backend/modules/moteur_thermique/calcul_gaz.py
from __future__ import annotations

import math
from typing import Any, Dict, Union

Number = Union[int, float]


# =============================================================================
# Validation (unique, robuste)
# =============================================================================

def _is_finite_number(x: Any) -> bool:
    # bool est un int en Python -> on l'exclut explicitement
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def _req_finite(name: str, x: Any) -> float:
    if not _is_finite_number(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _req_pos(name: str, x: Any, *, strictly: bool = True) -> float:
    v = _req_finite(name, x)
    if strictly:
        if v <= 0.0:
            raise ValueError(f"{name} doit être > 0 (reçu: {v}).")
    else:
        if v < 0.0:
            raise ValueError(f"{name} doit être >= 0 (reçu: {v}).")
    return v


# =============================================================================
# Loi des gaz parfaits (forme massique) + adiabatique (gaz parfait)
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

    Contraintes physiques / robustesse :
    - m >= 0
    - V > 0
    - T > 0 (K)
    - R > 0 (J/(kg·K))
    """
    m = _req_pos("masse_kg", masse_kg, strictly=False)
    V = _req_pos("volume_m3", volume_m3, strictly=True)
    T = _req_pos("temperature_k", temperature_k, strictly=True)
    R = _req_pos("constante_gaz_r", constante_gaz_r, strictly=True)

    P = (m * R * T) / V

    if not return_details:
        return P

    rho = (m / V) if V > 0 else float("inf")
    return {
        "pression_pa": P,
        "masse_kg": m,
        "volume_m3": V,
        "temperature_k": T,
        "constante_gaz_r": R,
        "densite_kg_m3": rho,
    }


def calcul_temperature_compression_adiabatique(
    t1_k: Number,
    p1_pa: Number,
    p2_pa: Number,
    gamma: Number = 1.4,
    *,
    return_details: bool = False,
) -> float | Dict[str, float]:
    """
    Compression/détente adiabatique (isentropique) d'un gaz parfait :
      T2 = T1 * (P2/P1)^((γ - 1) / γ)

    Contraintes :
    - T1 > 0, P1 > 0, P2 > 0
    - γ > 1
    """
    T1 = _req_pos("t1_k", t1_k, strictly=True)
    P1 = _req_pos("p1_pa", p1_pa, strictly=True)
    P2 = _req_pos("p2_pa", p2_pa, strictly=True)
    g = _req_pos("gamma", gamma, strictly=True)

    if g <= 1.0:
        raise ValueError("gamma doit être strictement > 1 pour une transformation adiabatique réaliste.")

    rapport_p = P2 / P1
    exposant = (g - 1.0) / g
    T2 = T1 * (rapport_p ** exposant)

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


# =============================================================================
# Force gaz sur piston
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
      A_p = π * B² / 4
      F_g = p * A_p

    - allow_negative_pression=True : autorise p < 0 (dépression, convention)
    - allow_zero_alesage=True : autorise B >= 0 (force nulle si B=0)
    - clamp_non_negative=True : retourne max(0, F_g)
    """
    p = _req_finite("pression_pa", pression_pa)
    if (not allow_negative_pression) and p < 0.0:
        raise ValueError("pression_pa ne peut pas être négative (allow_negative_pression=False).")

    B = _req_pos("alesage_m", alesage_m, strictly=not allow_zero_alesage)
    aire_piston = (math.pi * (B ** 2)) / 4.0
    F = p * aire_piston

    if clamp_non_negative:
        F = max(0.0, F)

    if not return_details:
        return F

    return {
        "F_g": F,
        "pression_pa": p,
        "alesage_m": B,
        "aire_piston_m2": aire_piston,
    }


# =============================================================================
# Fuites (segments / jeu annulaire) : Poiseuille laminaire
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
    Débit volumique de fuite dans un jeu annulaire (laminaire, Poiseuille) :

      Q = (π * r * h³ * ΔP) / (6 * μ * L)

    - use_abs_delta_p=True : magnitude (Q>=0 si clamp_non_negative=True)
    - use_abs_delta_p=False : conserve le signe de ΔP (sens)
    """
    dP = _req_finite("delta_p_pa", delta_p_pa)
    h = _req_pos("jeu_radial_h_m", jeu_radial_h_m, strictly=False)
    r = _req_pos("rayon_m", rayon_m, strictly=False)
    L = _req_pos("longueur_fuite_l_m", longueur_fuite_l_m, strictly=True)
    mu = _req_pos("viscosite_dynamique_pa_s", viscosite_dynamique_pa_s, strictly=True)
    eps = _req_pos("epsilon", epsilon, strictly=True)

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

    return {
        "Q": Q,
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
    Débit massique de fuite :
      m_dot = ρ * Q

    - use_abs_debit=True : magnitude (m_dot>=0 si clamp_non_negative=True)
    - use_abs_debit=False : conserve le signe de Q
    """
    Q = _req_finite("debit_volumique_m3s", debit_volumique_m3s)
    rho = _req_pos("densite_kg_m3", densite_kg_m3, strictly=False)

    Q_eff = abs(Q) if use_abs_debit else Q
    m_dot = Q_eff * rho

    if use_abs_debit and clamp_non_negative:
        m_dot = max(0.0, m_dot)

    if not return_details:
        return m_dot

    return {
        "m_dot": m_dot,
        "debit_volumique_m3s": float(Q),
        "debit_volumique_eff_m3s": float(Q_eff),
        "densite_kg_m3": float(rho),
        "use_abs_debit": 1.0 if use_abs_debit else 0.0,
        "clamp_non_negative": 1.0 if clamp_non_negative else 0.0,
    }


__all__ = [
    "calcul_pression_gaz_parfait",
    "calcul_temperature_compression_adiabatique",
    "calcul_force_gaz",
    "calcul_debit_fuite_annulaire",
    "calcul_masse_fuite",
]
