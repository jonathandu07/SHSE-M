# backend\modules\boite_crabots\calcul_dimensionnement_arbre.py
from __future__ import annotations

import math
from typing import Literal, Optional


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


# =============================================================================
# Extensions ajoutées pour compléter le dimensionnement
# =============================================================================

def calcul_coefficient_securite(
    contrainte_von_mises_pa: float,
    limite_elastique_pa: float,
) -> float:
    """
    Calcule le coefficient de sécurité (Safety Factor).

    Formule : S = Re / σ_vm

    Paramètres :
    - contrainte_von_mises_pa : σ_vm (Pa) >= 0
    - limite_elastique_pa : Re ou Yield Strength (Pa) > 0

    Retour :
    - S (adimensionnel).
      - Si S < 1 : rupture/plastification probable.
      - Si S > 1 : marge de sécurité.
    """
    sigma_vm = _require_positive("contrainte_von_mises_pa", contrainte_von_mises_pa, strictly=False)
    Re = _require_positive("limite_elastique_pa", limite_elastique_pa, strictly=True)

    if sigma_vm == 0.0:
        return float("inf")  # Sécurité infinie si aucune contrainte

    return Re / sigma_vm


def calcul_angle_torsion(
    couple_nm: float,
    longueur_arbre_m: float,
    diametre_arbre_m: float,
    module_cisaillement_pa: float = 80e9,  # Acier typique (~80 GPa)
    *,
    use_abs_couple: bool = True,
) -> float:
    """
    Calcule l'angle de torsion total sur une longueur donnée.
    Utile pour vérifier la rigidité (désalignement des dents).

    Formule : θ (rad) = (T * L) / (G * J0)
    Avec J0 (moment quadratique polaire arbre plein) = (π * d^4) / 32

    => θ = (32 * T * L) / (π * G * d^4)

    Paramètres :
    - couple_nm : T
    - longueur_arbre_m : L
    - diametre_arbre_m : d
    - module_cisaillement_pa : G (Pa). Défaut 80 GPa (Acier).

    Retour :
    - Angle en RADIANS.
    """
    T = abs(_require_finite("couple_nm", couple_nm)) if use_abs_couple else _require_finite("couple_nm", couple_nm)
    L = _require_positive("longueur_arbre_m", longueur_arbre_m, strictly=True)
    d = _require_positive("diametre_arbre_m", diametre_arbre_m, strictly=True)
    G = _require_positive("module_cisaillement_pa", module_cisaillement_pa, strictly=True)

    theta_rad = (32.0 * T * L) / (math.pi * G * (d ** 4))
    return theta_rad


def estimer_diametre_minimal_von_mises(
    couple_nm: float,
    moment_flechissant_nm: float,
    limite_elastique_pa: float,
    coefficient_securite_cible: float = 1.5,
) -> float:
    """
    Estime le diamètre minimal requis pour résister aux charges selon Von Mises.

    Dérivation :
      σ_vm <= Re / S
      (16 / (π * d³)) * sqrt(4*M² + 3*T²) <= Re / S
      d³ >= (16 * S / (π * Re)) * sqrt(4*M² + 3*T²)

    Paramètres :
    - couple_nm : T
    - moment_flechissant_nm : M
    - limite_elastique_pa : Re (Pa)
    - coefficient_securite_cible : S (défaut 1.5)

    Retour :
    - Diamètre minimal (m)
    """
    T = abs(_require_finite("couple_nm", couple_nm))
    M = abs(_require_finite("moment_flechissant_nm", moment_flechissant_nm))
    Re = _require_positive("limite_elastique_pa", limite_elastique_pa, strictly=True)
    S = _require_positive("coefficient_securite_cible", coefficient_securite_cible, strictly=True)

    # Terme de charge combinée : sqrt(4M² + 3T²)
    charge_combinee = math.sqrt(4.0 * (M**2) + 3.0 * (T**2))

    # d^3
    d_cube = (16.0 * S * charge_combinee) / (math.pi * Re)

    return math.pow(d_cube, 1.0/3.0)