# backend\modules\moteur_thermique\calcul_loi_gaz_parfait.py
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
    """Exige x > 0 (ou x >= 0 si strict=False)."""
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_pression_gaz_parfait(
    masse_kg: float,
    volume_m3: float,
    temperature_k: float,
    constante_gaz_r: float = 287.05,
) -> float:
    """
    Calcule la pression d'un gaz parfait à partir de la masse, du volume et de la température.

    Loi des gaz parfaits (forme massique) :
      P = (m * R * T) / V

    Où :
    - P : pression (Pa)
    - m : masse du gaz (kg)
    - R : constante spécifique du gaz (J/(kg·K))
         (air sec : ~287.05 J/(kg·K) par défaut)
    - T : température absolue (K)
    - V : volume (m³)

    Contraintes physiques / robustesse :
    - V > 0 (sinon division par zéro)
    - T > 0 (température absolue)
    - R > 0 (constante physique)
    - m >= 0 (une masse négative n'a pas de sens en physique classique)
    """
    m = _exiger_positif("masse_kg", masse_kg, strict=False)
    V = _exiger_positif("volume_m3", volume_m3, strict=True)
    T = _exiger_positif("temperature_k", temperature_k, strict=True)
    R = _exiger_positif("constante_gaz_r", constante_gaz_r, strict=True)

    # Calcul direct : aucun changement de "return" (float), juste une validation renforcée.
    return (m * R * T) / V


def calcul_temperature_compression_adiabatique(
    t1_k: float,
    p1_pa: float,
    p2_pa: float,
    gamma: float = 1.4,
) -> float:
    """
    Calcule la température finale après une compression/détente adiabatique (gaz parfait).

    Relation adiabatique (isentropique) :
      T2 = T1 * (P2/P1)^((γ - 1) / γ)

    Où :
    - T1, T2 : températures absolues (K)
    - P1, P2 : pressions absolues (Pa)
    - γ : coefficient adiabatique (Cp/Cv) (air sec ~ 1.4)

    Contraintes physiques / robustesse :
    - T1 > 0, P1 > 0, P2 > 0
    - γ > 1 (sinon l'exposant et la physique deviennent incohérents)
    """
    T1 = _exiger_positif("t1_k", t1_k, strict=True)
    P1 = _exiger_positif("p1_pa", p1_pa, strict=True)
    P2 = _exiger_positif("p2_pa", p2_pa, strict=True)
    g = _exiger_positif("gamma", gamma, strict=True)

    if g <= 1.0:
        raise ValueError("gamma doit être strictement > 1 pour une transformation adiabatique réaliste.")

    rapport_p = P2 / P1
    exposant = (g - 1.0) / g

    # Calcul direct : conserve exactement le type de retour (float).
    return T1 * (rapport_p ** exposant)
