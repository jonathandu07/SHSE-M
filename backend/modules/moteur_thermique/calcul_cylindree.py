# backend\modules\moteur_thermique\calcul_cylindree.py
from __future__ import annotations

import math
from typing import Optional, Literal


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


def _require_int_ge(name: str, x: int, min_value: int = 1) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def calcul_cylindree_unitaire(
    alesage_m: float,
    course_m: float,
    *,
    # Options non intrusives : par défaut, même comportement "mathématique" que ton code, mais plus sûr.
    allow_zero: bool = False,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la cylindrée unitaire (volume balayé) d'un cylindre.

    Formule :
      V_d = (π * B² / 4) * S

    Paramètres (SI) :
    - alesage_m : B (m) diamètre d'alésage
    - course_m : S (m) course du piston
    - allow_zero : False (défaut) -> impose B>0 et S>0
                  True -> autorise B>=0 et/ou S>=0 (V_d peut alors être 0)
    - return_details : True -> renvoie aussi l'aire et les entrées normalisées

    Retour :
    - cylindrée unitaire V_d (m³) ou dict si return_details=True
    """
    if allow_zero:
        B = _require_positive("alesage_m", alesage_m, strictly=False)
        S = _require_positive("course_m", course_m, strictly=False)
    else:
        B = _require_positive("alesage_m", alesage_m, strictly=True)
        S = _require_positive("course_m", course_m, strictly=True)

    # Aire de section du cylindre A = π * (B/2)^2 = π*B²/4
    aire_section = (math.pi * (B ** 2)) / 4.0
    Vd = aire_section * S

    if return_details:
        return {
            "V_d": Vd,
            "alesage_m": B,
            "course_m": S,
            "aire_section_m2": aire_section,
        }
    return Vd


def calcul_cylindree_totale(
    cylindree_unitaire_m3: float,
    nombre_cylindres: int,
    *,
    allow_zero_cylindres: bool = False,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la cylindrée totale.

    Formule :
      V_tot = V_unit * N

    Paramètres :
    - cylindree_unitaire_m3 : V_unit (m³) (généralement >= 0)
    - nombre_cylindres : N (int)
    - allow_zero_cylindres : False (défaut) -> impose N>=1
                             True -> autorise N=0 (V_tot=0)
    - return_details : True -> renvoie aussi les entrées

    Retour :
    - cylindrée totale V_tot (m³) ou dict si return_details=True
    """
    V_unit = _require_finite("cylindree_unitaire_m3", cylindree_unitaire_m3)

    if allow_zero_cylindres:
        N = _require_int_ge("nombre_cylindres", nombre_cylindres, 0)
    else:
        N = _require_int_ge("nombre_cylindres", nombre_cylindres, 1)

    V_tot = V_unit * float(N)

    # On ne "clamp" pas par défaut : si un pipeline a une convention signée, on ne casse pas.
    if return_details:
        return {
            "V_tot": V_tot,
            "cylindree_unitaire_m3": V_unit,
            "nombre_cylindres": float(N),
        }
    return V_tot
