# backend\modules\moteur_thermique\calcul_vitesse_piston.py
from __future__ import annotations

import math


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
    Utile pour imposer des contraintes physiques (longueurs, vitesses...).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_vitesse_moyenne_piston(course_m: float, vitesse_rotation_tr_min: float) -> float:
    """
    Calcule la vitesse moyenne du piston (vitesse moyenne de translation sur un cycle).

    Formule (inchangée) :
      U_p = 2 * S * (n / 60)

    Où :
    - U_p : vitesse moyenne du piston (m/s)
    - S : course (m) (>= 0)
    - n : régime (tr/min) (>= 0)

    Justification :
    - Sur un tour, le piston parcourt 2*S (aller + retour).
    - Le nombre de tours par seconde vaut n/60.

    Robustesse :
    - Refuse NaN/inf.
    - Accepte course=0 ou n=0 (=> vitesse moyenne nulle).
    """
    S = _exiger_positif("course_m", course_m, strict=False)
    n = _exiger_positif("vitesse_rotation_tr_min", vitesse_rotation_tr_min, strict=False)

    return 2.0 * S * (n / 60.0)
