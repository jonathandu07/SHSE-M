# backend\modules\architecture\calcul_cylindree_admissible.py
from __future__ import annotations

import math


# =============================================================================
# Utilitaires robustesse (mêmes principes que tes autres modules)
# =============================================================================

def _est_fini(x: float) -> bool:
    """Vérifie qu'une valeur est un nombre réel fini (pas NaN, pas inf)."""
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _exiger_fini(nom: str, x: float) -> float:
    """Convertit en float et lève une erreur si NaN/inf."""
    if not _est_fini(x):
        raise ValueError(f"{nom} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _exiger_positif(nom: str, x: float, *, strict: bool = True) -> float:
    """
    Exige x > 0 (ou x >= 0 si strict=False).
    Utile pour imposer des contraintes physiques (vitesses, régimes, ratios...).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


# =============================================================================
# Calculs "admissibles" basés sur la vitesse moyenne piston
# =============================================================================

def calcul_bore_max_admissible(
    vitesse_piston_max_ms: float,
    regime_tr_min: float,
    ratio_course_alesage_max: float
) -> float:
    """
    Calcule l'alésage maximal admissible (B*) afin de ne pas dépasser une vitesse moyenne
    de piston limite, en utilisant une contrainte géométrique de type S/B <= r_max.

    On part de la définition de la vitesse moyenne du piston (moteur à manivelle) :
      U_p = 2 * S * (n / 60)

    Donc, si U_p <= U_p_max :
      2 * S * (n / 60) <= U_p_max
      S <= (30 * U_p_max) / n

    Ensuite, si l'on impose une limite géométrique :
      S / B <= r_max  (ici ratio_course_alesage_max)
      => B >= S / r_max  (attention : si r_max est un maximum, alors S = r_max * B)
      Pour un dimensionnement "max cylindrée sous contraintes", on prend généralement :
        S = r_max * B
      et donc :
        B = S / r_max

    On obtient :
      B_max = S_max / r_max
      avec S_max = (30 * U_p_max) / n

    Args:
        vitesse_piston_max_ms (float): Limite de vitesse moyenne piston (U_p_max) en m/s. (>= 0)
        regime_tr_min (float): Régime nominal n en tr/min. (>= 0)
        ratio_course_alesage_max (float): r_max = (S/B)_max. (> 0)

    Returns:
        float: Alésage maximal admissible B_max en mètres.
    """
    # Validation robuste (sans changer l'API ni le retour)
    Umax = _exiger_positif("vitesse_piston_max_ms", vitesse_piston_max_ms, strict=False)
    n = _exiger_positif("regime_tr_min", regime_tr_min, strict=False)
    r_max = _exiger_positif("ratio_course_alesage_max", ratio_course_alesage_max, strict=True)

    # Comportement stable : si n == 0, pas de mouvement => aucune contrainte dynamique,
    # mais la formule S_max = 30*Umax/n diverge. On retourne 0.0 comme ton code.
    if n == 0.0:
        return 0.0

    # Course maximale compatible avec U_p_max
    S_max = (30.0 * Umax) / n  # [m]

    # Alésage maximal sous contrainte géométrique S = r_max * B  => B = S / r_max
    B_max = S_max / r_max  # [m]

    # Par sécurité numérique : si Umax=0 => S_max=0 => B_max=0 (ok)
    return B_max


def calcul_cylindree_unit_max(bore_max_m: float, ratio_course_alesage_max: float) -> float:
    """
    Calcule la cylindrée unitaire maximale dérivée sous l'hypothèse que la course atteint
    la limite géométrique maximale (S = r_max * B).

    Cylindrée unitaire :
      V_d = (π/4) * B² * S

    En posant S = r_max * B :
      V_d_max = (π/4) * B³ * r_max

    Args:
        bore_max_m (float): Alésage maximal B_max en mètres. (>= 0)
        ratio_course_alesage_max (float): r_max = (S/B)_max. (> 0)

    Returns:
        float: Cylindrée unitaire maximale (m³).
    """
    B = _exiger_positif("bore_max_m", bore_max_m, strict=False)
    r_max = _exiger_positif("ratio_course_alesage_max", ratio_course_alesage_max, strict=True)

    # Vd = (pi/4) * B^3 * r_max
    return (math.pi / 4.0) * (B ** 3) * r_max
