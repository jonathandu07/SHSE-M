# backend\modules\architecture\calcul_nombre_cylindres_min.py
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
    Utile pour imposer des contraintes physiques (volumes, limites unitaires...).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


# =============================================================================
# Nombre minimal de cylindres
# =============================================================================

def calcul_nombre_cylindres_min(cylindree_totale_m3: float, cylindree_unitaire_max_m3: float) -> int:
    """
    Calcule le nombre minimal de cylindres requis pour atteindre une cylindrée totale donnée,
    sans dépasser une limite admissible de cylindrée unitaire (liée à vitesse piston, alésage, etc.).

    Déduction (pour enlever les "inconnues") :
    - On veut V_tot <= N * V_u_max
      => N >= V_tot / V_u_max
      => N_min = ceil(V_tot / V_u_max)

    Args:
        cylindree_totale_m3 (float): Cylindrée totale requise V_tot (m³). (>= 0)
        cylindree_unitaire_max_m3 (float): Cylindrée unitaire maximale admissible V_u_max (m³). (> 0)

    Returns:
        int: Nombre minimal de cylindres (>= 0).

    Compatibilité / comportement historique :
    - Ton code renvoyait 999 si V_u_max <= 0 (valeur sentinelle).
      On conserve ce comportement EXACT pour ne pas casser les appels existants.
    """
    V_tot = _exiger_positif("cylindree_totale_m3", cylindree_totale_m3, strict=False)

    # Comportement conservé : sentinelle si invalide
    if not _est_fini(cylindree_unitaire_max_m3) or cylindree_unitaire_max_m3 <= 0.0:
        return 999

    V_u_max = float(cylindree_unitaire_max_m3)

    # Cas stable : si V_tot == 0 => 0 cylindre requis (math.ceil(0)=0)
    ratio = V_tot / V_u_max
    return int(math.ceil(ratio))
