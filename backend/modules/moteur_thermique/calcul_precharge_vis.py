# backend\modules\moteur_thermique\calcul_precharge_vis.py
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
    Utile pour imposer des contraintes physiques (pressions, surfaces, diamètres...).
    """
    x = _exiger_fini(nom, x)
    ok = x > 0.0 if strict else x >= 0.0
    if not ok:
        op = ">" if strict else ">="
        raise ValueError(f"{nom} doit être {op} 0 (reçu: {x}).")
    return x


def calcul_force_separation(pression_max_pa: float, aire_effective_m2: float) -> float:
    """
    Calcule la force de séparation exercée sur un couvercle sous pression interne.

    Formule (inchangée) :
      F_sep = p_max * A_eff

    Où :
    - F_sep : force de séparation (N)
    - p_max : pression maximale (Pa) (>= 0)
    - A_eff : aire effective soumise à la pression (m²) (>= 0)

    Remarque :
    - Si p_max = 0 ou A_eff = 0 => F_sep = 0.
    """
    p = _exiger_positif("pression_max_pa", pression_max_pa, strict=False)
    A = _exiger_positif("aire_effective_m2", aire_effective_m2, strict=False)
    return p * A


def calcul_precharge_vis_totale(
    force_separation_n: float,
    force_joint_n: float,
    facteur_securite: float = 1.5,
) -> float:
    """
    Calcule la précharge totale requise sur l'ensemble des vis.

    Formule (inchangée) :
      F_pre_tot >= γ * F_sep + F_joint

    Où :
    - F_pre_tot : précharge totale (N)
    - γ : facteur de sécurité (> 0), typiquement 1.2 à 2 selon criticité
    - F_sep : force de séparation (N) (>= 0)
    - F_joint : effort nécessaire au serrage/écrasement du joint (N) (>= 0)

    Remarque :
    - Cette relation est un dimensionnement global simplifié.
      En pratique, on peut aussi tenir compte du nombre de vis, de la raideur vis/pièce,
      et du relâchement sous charge (méthode de raideurs).
    """
    F_sep = _exiger_positif("force_separation_n", force_separation_n, strict=False)
    F_joint = _exiger_positif("force_joint_n", force_joint_n, strict=False)
    gamma = _exiger_positif("facteur_securite", facteur_securite, strict=True)

    return (gamma * F_sep) + F_joint


def calcul_couple_serrage(
    force_precharge_vis_n: float,
    diametre_nominal_m: float,
    facteur_frottement_k: float = 0.2,
) -> float:
    """
    Estime le couple de serrage nécessaire pour atteindre une précharge donnée.

    Formule (inchangée, approximation "écrou K") :
      M = K * F * d

    Où :
    - M : couple de serrage (N·m)
    - K : facteur de frottement global (sans dimension) (>= 0)
         (dépend fortement lubrification / état de surface / filetage)
    - F : force de précharge (N) (>= 0)
    - d : diamètre nominal (m) (> 0)

    Remarque importante :
    - Cette formule est une approximation industrielle très utilisée,
      mais K peut varier fortement (±30% voire plus). Pour un calcul plus fin :
      prendre en compte frottement filet + portée, pas, angle d'hélice, etc.
    """
    F = _exiger_positif("force_precharge_vis_n", force_precharge_vis_n, strict=False)
    d = _exiger_positif("diametre_nominal_m", diametre_nominal_m, strict=True)
    K = _exiger_positif("facteur_frottement_k", facteur_frottement_k, strict=False)

    return K * F * d
