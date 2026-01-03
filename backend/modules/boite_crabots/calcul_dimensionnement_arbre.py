# backend\modules\boite_crabots\calcul_dimensionnement_arbre.py
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


def calcul_contrainte_cisaillement_torsion(
    couple_nm: float,
    diametre_arbre_m: float,
    *,
    use_abs_couple: bool = True,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la contrainte de cisaillement maximale due à la torsion d'un arbre plein circulaire.

    Formule (arbre plein) :
      τ_max = (16 * T) / (π * d³)

    Paramètres :
    - couple_nm : T (N·m). Peut être signé ; par défaut on utilise |T| (magnitude).
    - diametre_arbre_m : d (m) > 0
    - use_abs_couple : True -> utilise |T| (défaut, plus robuste si convention signée)
    - clamp_non_negative : True -> borne τ >= 0

    Retour :
    - τ_max (Pa)
    """
    T = _require_finite("couple_nm", couple_nm)
    d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)

    T_eff = abs(T) if use_abs_couple else T
    tau = (16.0 * T_eff) / (math.pi * (d ** 3))

    return max(0.0, tau) if clamp_non_negative else tau


def calcul_contrainte_flexion_arbre(
    moment_flechissant_nm: float,
    diametre_arbre_m: float,
    *,
    use_abs_moment: bool = True,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la contrainte normale maximale due à la flexion d'un arbre plein circulaire.

    Formule (arbre plein) :
      σ_b = (32 * M) / (π * d³)

    Paramètres :
    - moment_flechissant_nm : M (N·m). Peut être signé ; par défaut on utilise |M|.
    - diametre_arbre_m : d (m) > 0
    - use_abs_moment : True -> utilise |M| (défaut)
    - clamp_non_negative : True -> borne σ >= 0

    Retour :
    - σ_b (Pa)
    """
    M = _require_finite("moment_flechissant_nm", moment_flechissant_nm)
    d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)

    M_eff = abs(M) if use_abs_moment else M
    sigma_b = (32.0 * M_eff) / (math.pi * (d ** 3))

    return max(0.0, sigma_b) if clamp_non_negative else sigma_b


def calcul_von_mises_arbre(
    contrainte_flexion: float,
    contrainte_cisaillement: float,
    *,
    mode: Literal["flexion+torsion", "general"] = "flexion+torsion",
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la contrainte équivalente de Von Mises.

    Cas flexion + torsion (classique arbre) :
      σ_eq = sqrt( σ_b² + 3 * τ² )

    Paramètres :
    - contrainte_flexion : σ_b (Pa) (souvent >= 0 si c'est une magnitude)
    - contrainte_cisaillement : τ (Pa)
    - mode :
        - "flexion+torsion" (défaut) : utilise sqrt(σ² + 3τ²)
        - "general" : alias, même calcul ici (réservé à extension future)
    - clamp_non_negative : borne σ_eq >= 0

    Retour :
    - σ_eq (Pa)
    """
    sigma = _require_finite("contrainte_flexion", contrainte_flexion)
    tau = _require_finite("contrainte_cisaillement", contrainte_cisaillement)

    if mode not in ("flexion+torsion", "general"):
        raise ValueError("mode doit être 'flexion+torsion' ou 'general'.")

    sigma_eq = math.sqrt((sigma ** 2) + 3.0 * (tau ** 2))
    return max(0.0, sigma_eq) if clamp_non_negative else sigma_eq
