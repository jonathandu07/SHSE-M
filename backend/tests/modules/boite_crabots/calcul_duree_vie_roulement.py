# backend\modules\boite_crabots\calcul_duree_vie_roulement.py
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


def calcul_charge_equivalente_roulement(
    force_radiale: float,
    force_axiale: float,
    facteur_x: float,
    facteur_y: float,
    *,
    use_abs_forces: bool = True,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la charge dynamique équivalente P.

    Formule (ISO/usage courant) :
      P = X * F_r + Y * F_a

    Paramètres :
    - force_radiale : F_r (N) (peut être signée selon convention)
    - force_axiale  : F_a (N) (peut être signée)
    - facteur_x : X (sans unité)
    - facteur_y : Y (sans unité)
    - use_abs_forces : True (défaut) -> utilise |F_r| et |F_a| (plus robuste)
    - clamp_non_negative : True -> borne P à >= 0

    Retour :
    - charge équivalente P (N)
    """
    Fr = _require_finite("force_radiale", force_radiale)
    Fa = _require_finite("force_axiale", force_axiale)
    X = _require_finite("facteur_x", facteur_x)
    Y = _require_finite("facteur_y", facteur_y)

    if use_abs_forces:
        Fr = abs(Fr)
        Fa = abs(Fa)

    P = X * Fr + Y * Fa
    return max(0.0, P) if clamp_non_negative else P


def calcul_duree_vie_l10(
    charge_dynamique_base_c: float,
    charge_equivalente_p: float,
    type_roulement: str = "bille",
    *,
    exposant_p: Optional[float] = None,
    epsilon: float = 1e-12,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la durée de vie L10 en millions de tours.

    Formule :
      L10 = (C / P)^p

    Valeurs usuelles :
      p = 3      pour roulements à billes
      p = 10/3   pour roulements à rouleaux

    Paramètres :
    - charge_dynamique_base_c : C (N) > 0
    - charge_equivalente_p : P (N)
    - type_roulement : 'bille' ou 'rouleau' (ou autres si exposant_p est fourni)
    - exposant_p : si fourni, remplace le choix par type_roulement
    - epsilon : seuil anti-division par 0 (si P <= epsilon => vie infinie théorique)
    - clamp_non_negative : borne L10 à >= 0

    Retour :
    - L10 (millions de tours)
    """
    C = _require_positive("charge_dynamique_base_c", charge_dynamique_base_c, strictly=True)
    P = _require_finite("charge_equivalente_p", charge_equivalente_p)
    eps = _require_positive("epsilon", epsilon, strictly=True)

    # Choix de l'exposant
    if exposant_p is not None:
        p = _require_positive("exposant_p", exposant_p, strictly=True)
    else:
        t = (type_roulement or "").strip().lower()
        if t == "bille":
            p = 3.0
        elif t == "rouleau":
            p = 10.0 / 3.0
        else:
            raise ValueError("Type de roulement inconnu (utiliser 'bille' ou 'rouleau', ou fournir exposant_p).")

    # Charge nulle (ou très faible) -> vie infinie théorique
    if abs(P) <= eps:
        return float("inf")

    # Si P est négative (convention de signe), on prend la magnitude pour éviter un ratio négatif.
    P_eff = abs(P)

    L10 = (C / P_eff) ** p
    return max(0.0, L10) if clamp_non_negative else L10


def calcul_duree_vie_heures(
    l10_millions: float,
    vitesse_rotation_tr_min: float,
    *,
    clamp_non_negative: bool = True,
    epsilon_n: float = 1e-12,
) -> float:
    """
    Convertit L10 (millions de tours) en durée de vie en heures.

    Formule :
      L10h = (10^6 * L10) / (60 * n_rpm)

    Paramètres :
    - l10_millions : L10 en millions de tours (peut être inf)
    - vitesse_rotation_tr_min : n (tr/min) > 0
    - epsilon_n : seuil anti-division par ~0
    - clamp_non_negative : borne à >= 0

    Retour :
    - durée de vie (heures)
    """
    L10 = _require_finite("l10_millions", l10_millions)
    n = _require_finite("vitesse_rotation_tr_min", vitesse_rotation_tr_min)
    epsn = _require_positive("epsilon_n", epsilon_n, strictly=True)

    if math.isinf(L10):
        return float("inf")

    if n <= epsn:
        raise ValueError("Vitesse doit être positive.")

    L10h = (1_000_000.0 * L10) / (60.0 * n)
    return max(0.0, L10h) if clamp_non_negative else L10h
