# backend\modules\moteur_thermique\calcul_force_gaz.py
from __future__ import annotations

import math
from typing import Optional


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


def calcul_force_gaz(
    pression_pa: float,
    alesage_m: float,
    *,
    # Options non intrusives : par défaut, même résultat que ton code (F = p * πB²/4)
    allow_negative_pression: bool = True,
    allow_zero_alesage: bool = False,
    clamp_non_negative: bool = False,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la force exercée par les gaz sur le piston.

    Formules :
      A_p = π * B² / 4
      F_g = p * A_p

    Paramètres :
    - pression_pa : p (Pa). Peut être signée (dépression) selon conventions :
        - allow_negative_pression=True (défaut) : autorise p < 0
        - allow_negative_pression=False : lève une erreur si p < 0
    - alesage_m : B (m) diamètre du piston :
        - par défaut B > 0
        - allow_zero_alesage=True autorise B >= 0 (force nulle si B=0)
    - clamp_non_negative : True -> force retournée bornée à >= 0 (magnitude)
    - return_details : True -> renvoie aussi A_p et les valeurs normalisées

    Retour :
    - F_g (N) ou dict si return_details=True
    """
    p = _require_finite("pression_pa", pression_pa)

    if not allow_negative_pression and p < 0.0:
        raise ValueError("pression_pa ne peut pas être négative (allow_negative_pression=False).")

    if allow_zero_alesage:
        B = _require_positive("alesage_m", alesage_m, strictly=False)
    else:
        B = _require_positive("alesage_m", alesage_m, strictly=True)

    aire_piston = (math.pi * (B ** 2)) / 4.0
    F = p * aire_piston

    if clamp_non_negative:
        F = max(0.0, F)

    if return_details:
        return {
            "F_g": F,
            "pression_pa": p,
            "alesage_m": B,
            "aire_piston_m2": aire_piston,
        }
    return F
