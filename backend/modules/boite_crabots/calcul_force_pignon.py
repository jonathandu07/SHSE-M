# backend\modules\boite_crabots\calcul_force_pignon.py
from __future__ import annotations

import math
from typing import Literal


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


def calcul_force_tangentielle(
    couple_nm: float,
    diametre_primitif_m: float,
    *,
    use_abs_couple: bool = True,
    epsilon: float = 1e-18,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule l'effort tangentiel sur un pignon.

    Formule :
      F_t = 2 * T / d

    Paramètres :
    - couple_nm : T (N·m). Peut être signé ; par défaut on utilise |T| (magnitude).
    - diametre_primitif_m : d (m) > 0
    - use_abs_couple : True (défaut) -> utilise |T|
    - epsilon : seuil anti-division par ~0
    - clamp_non_negative : True -> borne F_t à >= 0

    Retour :
    - force tangentielle F_t (N)
    """
    T = _require_finite("couple_nm", couple_nm)
    d = _require_positive("diametre_primitif_m", diametre_primitif_m, strictly=True)
    eps = _require_positive("epsilon", epsilon, strictly=True)

    if d <= eps:
        raise ValueError("Le diamètre primitif est trop petit (risque de division par ~0).")

    T_eff = abs(T) if use_abs_couple else T
    Ft = (2.0 * T_eff) / d

    return max(0.0, Ft) if clamp_non_negative else Ft


def calcul_forces_engrenage(
    force_tangentielle: float,
    angle_pression_deg: float = 20.0,
    angle_helice_deg: float = 0.0,
    *,
    output: Literal["FR_FA", "FT_FR_FA"] = "FR_FA",
    use_abs_force: bool = True,
    epsilon_cos: float = 1e-12,
    clamp_non_negative: bool = False,
) -> dict[str, float]:
    """
    Calcule les composantes radiale et axiale des efforts d'engrenage.

    Formules (simplifiées, engrenages cylindriques) :
      F_r = F_t * tan(phi) / cos(beta)
      F_a = F_t * tan(beta)

    Paramètres :
    - force_tangentielle : F_t (N). Peut être signée ; par défaut on utilise |F_t|.
    - angle_pression_deg : phi (°), standard 20°
    - angle_helice_deg : beta (°), 0° pour denture droite
    - output :
        - "FR_FA" (défaut) -> renvoie {"F_r":..., "F_a":...}
        - "FT_FR_FA" -> renvoie aussi F_t
    - use_abs_force : True (défaut) -> utilise |F_t| pour éviter des composantes signées involontaires
    - epsilon_cos : seuil pour éviter division par ~0 si cos(beta) ~ 0 (beta proche de 90°)
    - clamp_non_negative :
        True -> borne F_r et F_a à >= 0 (utile si tu veux uniquement des magnitudes)

    Retour :
    - dict avec F_r, F_a (et éventuellement F_t)
    """
    Ft = _require_finite("force_tangentielle", force_tangentielle)
    phi_deg = _require_finite("angle_pression_deg", angle_pression_deg)
    beta_deg = _require_finite("angle_helice_deg", angle_helice_deg)
    epsc = _require_positive("epsilon_cos", epsilon_cos, strictly=True)

    Ft_eff = abs(Ft) if use_abs_force else Ft

    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)

    cos_beta = math.cos(beta)
    if abs(cos_beta) <= epsc:
        raise ValueError("cos(beta) trop proche de 0 : angle_helice_deg trop élevé (division instable).")

    Fr = (Ft_eff * math.tan(phi)) / cos_beta
    Fa = Ft_eff * math.tan(beta)

    if clamp_non_negative:
        Fr = max(0.0, Fr)
        Fa = max(0.0, Fa)

    if output == "FR_FA":
        return {"F_r": Fr, "F_a": Fa}
    if output == "FT_FR_FA":
        return {"F_t": Ft_eff, "F_r": Fr, "F_a": Fa}

    raise ValueError("output doit être 'FR_FA' ou 'FT_FR_FA'.")
