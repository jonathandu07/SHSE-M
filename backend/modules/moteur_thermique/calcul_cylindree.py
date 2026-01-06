# backend\modules\moteur_thermique\calcul_cylindree.py
from __future__ import annotations

import math
from typing import Optional, Literal, Union, Dict


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
    allow_zero: bool = False,
    return_details: bool = False,
) -> Union[float, Dict[str, float]]:
    """
    Calcule la cylindrée unitaire (volume balayé) d'un cylindre.

    Formule :
      V_d = (π * B² / 4) * S

    Paramètres (SI) :
    - alesage_m : B (m) diamètre d'alésage
    - course_m : S (m) course du piston
    - allow_zero : False (défaut) -> impose B>0 et S>0
    - return_details : True -> renvoie aussi l'aire et les entrées normalisées

    Retour :
    - cylindrée unitaire V_d (m³) ou dict
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
) -> Union[float, Dict[str, float]]:
    """
    Calcule la cylindrée totale.

    Formule :
      V_tot = V_unit * N

    Paramètres :
    - cylindree_unitaire_m3 : V_unit (m³)
    - nombre_cylindres : N (int)
    - return_details : True -> renvoie aussi les entrées

    Retour :
    - cylindrée totale V_tot (m³) ou dict
    """
    V_unit = _require_finite("cylindree_unitaire_m3", cylindree_unitaire_m3)

    if allow_zero_cylindres:
        N = _require_int_ge("nombre_cylindres", nombre_cylindres, 0)
    else:
        N = _require_int_ge("nombre_cylindres", nombre_cylindres, 1)

    V_tot = V_unit * float(N)

    if return_details:
        return {
            "V_tot": V_tot,
            "cylindree_unitaire_m3": V_unit,
            "nombre_cylindres": float(N),
        }
    return V_tot


# =============================================================================
# Extensions Ajoutées : Géométrie et Taux de Compression
# =============================================================================

def calcul_volume_mort(
    cylindree_unitaire_m3: float,
    taux_compression: float,
) -> float:
    """
    Calcule le volume mort (volume chambre combustion au PMH) à partir du taux de compression.

    Dérivation :
      CR = (V_d + V_c) / V_c
      CR * V_c = V_d + V_c
      V_c * (CR - 1) = V_d
      V_c = V_d / (CR - 1)

    Paramètres :
    - cylindree_unitaire_m3 : V_d (m³) > 0
    - taux_compression : CR (adimensionnel) > 1

    Retour :
    - V_c (m³)
    """
    Vd = _require_positive("cylindree_unitaire_m3", cylindree_unitaire_m3, strictly=True)
    CR = _require_finite("taux_compression", taux_compression)

    if CR <= 1.0:
        raise ValueError(f"taux_compression doit être > 1.0 (reçu: {CR}).")

    return Vd / (CR - 1.0)


def calcul_taux_compression(
    cylindree_unitaire_m3: float,
    volume_mort_m3: float,
) -> float:
    """
    Calcule le taux de compression géométrique.

    Formule :
      CR = (V_d + V_c) / V_c

    Paramètres :
    - cylindree_unitaire_m3 : V_d (m³) >= 0
    - volume_mort_m3 : V_c (m³) > 0

    Retour :
    - CR (ratio)
    """
    Vd = _require_positive("cylindree_unitaire_m3", cylindree_unitaire_m3, strictly=False)
    Vc = _require_positive("volume_mort_m3", volume_mort_m3, strictly=True)

    return (Vd + Vc) / Vc


def calcul_ratio_alesage_course(
    alesage_m: float,
    course_m: float,
    return_details: bool = False
) -> Union[float, Dict[str, Any]]:
    """
    Calcule le ratio Alésage/Course pour déterminer l'architecture moteur.

    R = B / S

    Interprétation :
    - R = 1 : Moteur Carré (Square)
    - R < 1 : Moteur Longue Course (Under-square) -> Favorise le couple à bas régime
    - R > 1 : Moteur Super Carré (Over-square) -> Favorise la puissance à haut régime

    Retour :
    - Ratio (float) ou Dict avec description textuelle.
    """
    B = _require_positive("alesage_m", alesage_m, strictly=True)
    S = _require_positive("course_m", course_m, strictly=True)

    ratio = B / S

    if return_details:
        if abs(ratio - 1.0) < 0.01:
            arch = "Carre"
        elif ratio < 1.0:
            arch = "Longue_Course"
        else:
            arch = "Super_Carre"
        
        return {
            "ratio": ratio,
            "architecture": arch,
            "alesage_m": B,
            "course_m": S
        }
    
    return ratio