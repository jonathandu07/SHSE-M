# backend\modules\moteur_thermique\calcul_pertes_frottement.py
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
    Utile pour imposer des contraintes physiques (vitesses, charges, coefficients, etc.).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_puissance_frottement_segment(
    force_normale_n: float,
    vitesse_moyenne_ms: float,
    coef_frottement: float,
) -> float:
    """
    Estime la puissance dissipée par frottement au niveau d'un segment (ou joint).

    Modèle simple de frottement sec / Coulomb (approximation utile en pré-dimensionnement) :
      P_f = μ * N * v

    Où :
    - P_f : puissance dissipée (W)
    - μ : coefficient de frottement (sans dimension)
    - N : force normale de contact (N)
    - v : vitesse de glissement moyenne (m/s)

    Robustesse / contraintes physiques :
    - μ >= 0
    - N >= 0 (on accepte 0 -> puissance nulle)
    - v >= 0 (si un appelant fournit une vitesse signée, il doit passer la magnitude)
    """
    mu = _exiger_positif("coef_frottement", coef_frottement, strict=False)
    N = _exiger_positif("force_normale_n", force_normale_n, strict=False)
    v = _exiger_positif("vitesse_moyenne_ms", vitesse_moyenne_ms, strict=False)

    # Retour float inchangé : aucun "return" renommé / aucune structure modifiée.
    return mu * N * v


def calcul_puissance_frottement_palier(
    charge_w: float,
    vitesse_glissement_ms: float,
    coef_frottement_f: float,
) -> float:
    """
    Estime la puissance dissipée dans un palier lisse (journal bearing) via un modèle simplifié.

    Modèle de frottement (approximation) :
      P_f = f * W * v

    Où :
    - P_f : puissance dissipée (W)
    - f : coefficient de frottement (sans dimension, dépend du régime de lubrification)
    - W : charge sur le palier (N)
    - v : vitesse de glissement (m/s)

    Robustesse / contraintes physiques :
    - f >= 0
    - W >= 0
    - v >= 0
    """
    f = _exiger_positif("coef_frottement_f", coef_frottement_f, strict=False)
    W = _exiger_positif("charge_w", charge_w, strict=False)
    v = _exiger_positif("vitesse_glissement_ms", vitesse_glissement_ms, strict=False)

    return f * W * v
