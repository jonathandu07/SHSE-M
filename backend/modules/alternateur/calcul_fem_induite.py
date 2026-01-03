# backend\modules\alternateur\calcul_fem_induite.py
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


def _require_int_ge(name: str, x: int, min_value: int = 0) -> int:
    if not isinstance(x, int):
        raise ValueError(f"{name} doit être un entier (reçu: {x!r}).")
    if x < min_value:
        raise ValueError(f"{name} doit être >= {min_value} (reçu: {x}).")
    return x


def calcul_fem_induite(
    frequence: float,
    nombre_spires_serie: int,
    flux_max_pole: float,
    facteur_enroulement: float,
    *,
    constante: float = 4.44,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la force électromotrice (f.e.m.) induite efficace par phase.

    Formule (sinusoïdale) :
      E_ph = C * f * N * Phi_max * k_w
      avec C = 4.44 (valeur classique en RMS pour une onde sinusoïdale)

    Paramètres :
    - frequence : f (Hz) >= 0
    - nombre_spires_serie : N (entier) >= 0
    - flux_max_pole : Phi_max (Wb) (peut être négatif selon convention -> valeur absolue souvent utilisée)
    - facteur_enroulement : k_w (souvent ~0.9 à 1.0, mais on ne bloque pas à un intervalle serré)
    - constante : C (par défaut 4.44). Permet d'adapter si forme d'onde/modèle différent.
    - clamp_non_negative : True -> retourne |E| (utile si flux ou k_w ont un signe de convention)

    Retour :
    - Tension efficace induite par phase (V)
    """
    f = _require_positive("frequence", frequence, strictly=False)
    N = _require_int_ge("nombre_spires_serie", nombre_spires_serie, 0)
    phi = _require_finite("flux_max_pole", flux_max_pole)
    kw = _require_finite("facteur_enroulement", facteur_enroulement)
    C = _require_positive("constante", constante, strictly=True)

    E = C * f * float(N) * phi * kw
    return abs(E) if clamp_non_negative else E


def calcul_fem_induite_avec_induction(
    frequence: float,
    nombre_spires_serie: int,
    induction_gap: float,
    aire_pole: float,
    facteur_enroulement: float,
    *,
    constante: float = 4.44,
    clamp_non_negative: bool = True,
    flux_model: Literal["B*A", "abs(B)*A"] = "B*A",
) -> float:
    """
    Calcule la f.e.m. induite en utilisant l'induction dans l'entrefer.

    Approximation :
      Phi_max ≈ B_g * A_p
      donc E_ph = C * f * N * B_g * A_p * k_w

    Paramètres :
    - induction_gap : B_g (T)
    - aire_pole : A_p (m²) >= 0
    - flux_model :
        - "B*A"       -> Phi = B*A (conserve le signe de B)
        - "abs(B)*A"  -> Phi = |B|*A (retourne une valeur positive de flux)

    Retour :
    - Tension efficace induite par phase (V)
    """
    f = _require_positive("frequence", frequence, strictly=False)
    N = _require_int_ge("nombre_spires_serie", nombre_spires_serie, 0)
    B = _require_finite("induction_gap", induction_gap)
    A = _require_positive("aire_pole", aire_pole, strictly=False)
    kw = _require_finite("facteur_enroulement", facteur_enroulement)
    C = _require_positive("constante", constante, strictly=True)

    if flux_model == "abs(B)*A":
        phi = abs(B) * A
    elif flux_model == "B*A":
        phi = B * A
    else:
        raise ValueError("flux_model doit être 'B*A' ou 'abs(B)*A'.")

    E = C * f * float(N) * phi * kw
    return abs(E) if clamp_non_negative else E
