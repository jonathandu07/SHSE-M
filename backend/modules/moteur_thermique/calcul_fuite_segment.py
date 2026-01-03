# backend\modules\moteur_thermique\calcul_fuite_segment.py
from __future__ import annotations

import math


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: float) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_positive(name: str, x: float, *, strictly: bool = True) -> float:
    x = _require_finite(name, x)
    ok = x > 0.0 if strictly else x >= 0.0
    if not ok:
        op = ">" if strictly else ">="
        raise ValueError(f"{name} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_debit_fuite_annulaire(
    delta_p_pa: float,
    jeu_radial_h_m: float,
    rayon_m: float,
    longueur_fuite_l_m: float,
    viscosite_dynamique_pa_s: float,
    *,
    # Options non intrusives : défaut = résultat identique (float Q)
    use_abs_delta_p: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule le débit de fuite volumique dans un jeu annulaire (Laminaire, Poiseuille).

    Formule (historique, inchangée) :
      Q = (π * r * h³ * ΔP) / (6 * μ * L)

    Compatibilité API :
    - Par défaut (return_details=False) : retourne un float (Q) comme avant.
    - En mode détails (return_details=True) : retourne un dict contenant :
        - "Q" : le débit (clé compatible avec l'usage historique si tu logs/pars un dict)
        - "_details" : infos supplémentaires (sans casser une éventuelle lecture future)

    Remarques :
    - use_abs_delta_p=True retourne une magnitude (Q >= 0 si clamp_non_negative=True).
    - use_abs_delta_p=False conserve le signe de ΔP (sens de fuite).
    """
    dP = _require_finite("delta_p_pa", delta_p_pa)
    h = _require_positive("jeu_radial_h_m", jeu_radial_h_m, strictly=False)
    r = _require_positive("rayon_m", rayon_m, strictly=False)
    L = _require_positive("longueur_fuite_l_m", longueur_fuite_l_m, strictly=True)
    mu = _require_positive("viscosite_dynamique_pa_s", viscosite_dynamique_pa_s, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)

    if L <= eps:
        raise ValueError("longueur_fuite_l_m trop petite (risque de division par ~0).")
    if mu <= eps:
        raise ValueError("viscosite_dynamique_pa_s trop petite (risque de division par ~0).")

    dP_eff = abs(dP) if use_abs_delta_p else dP

    numerateur = math.pi * r * (h ** 3) * dP_eff
    denominateur = 6.0 * mu * L

    Q = numerateur / denominateur

    # Si on a conservé le signe, on ne force pas Q>=0
    if use_abs_delta_p and clamp_non_negative:
        Q = max(0.0, Q)

    if not return_details:
        return Q

    return {
        "Q": Q,
        "_details": {
            "delta_p_pa": dP,
            "delta_p_eff_pa": dP_eff,
            "jeu_radial_h_m": h,
            "rayon_m": r,
            "longueur_fuite_l_m": L,
            "viscosite_dynamique_pa_s": mu,
            "numerateur": numerateur,
            "denominateur": denominateur,
            "use_abs_delta_p": bool(use_abs_delta_p),
            "clamp_non_negative": bool(clamp_non_negative),
            "epsilon": eps,
        },
    }


def calcul_masse_fuite(
    debit_volumique_m3s: float,
    densite_kg_m3: float,
    *,
    # Options non intrusives : défaut = résultat identique (float ṁ)
    use_abs_debit: bool = True,
    clamp_non_negative: bool = True,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule le débit massique de fuite.

    Formule (historique, inchangée) :
      ṁ = ρ * Q

    Compatibilité API :
    - Par défaut (return_details=False) : retourne un float (ṁ) comme avant.
    - En mode détails (return_details=True) : retourne un dict contenant :
        - "m_dot" : le débit massique (clé stable)
        - "_details" : infos supplémentaires

    Remarque :
    - use_abs_debit=True retourne une magnitude (ṁ >= 0 si clamp_non_negative=True).
    - use_abs_debit=False conserve le signe de Q.
    """
    Q = _require_finite("debit_volumique_m3s", debit_volumique_m3s)
    rho = _require_positive("densite_kg_m3", densite_kg_m3, strictly=False)

    Q_eff = abs(Q) if use_abs_debit else Q
    m_dot = Q_eff * rho

    if use_abs_debit and clamp_non_negative:
        m_dot = max(0.0, m_dot)

    if not return_details:
        return m_dot

    return {
        "m_dot": m_dot,
        "_details": {
            "debit_volumique_m3s": Q,
            "debit_volumique_eff_m3s": Q_eff,
            "densite_kg_m3": rho,
            "use_abs_debit": bool(use_abs_debit),
            "clamp_non_negative": bool(clamp_non_negative),
        },
    }
