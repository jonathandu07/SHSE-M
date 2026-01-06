from __future__ import annotations

import math

_G0 = 9.80665  # m/s²


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


def _require_eta(name: str, eta: float) -> float:
    eta = _require_finite(name, eta)
    if not (0.0 < eta <= 1.0):
        raise ValueError(f"{name} doit être dans (0, 1] (reçu: {eta}).")
    return eta


def calcul_puissance_moteur_electrique(
    puissance_roue_w: float,
    rendement_transmission: float,
    *,
    pertes_fixes_w: float = 0.0,
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la puissance moteur nécessaire à partir de la puissance à la roue.

    Modèle de base :
      P_motor = (P_wheel + pertes_fixes) / eta_trans

    Paramètres :
    - puissance_roue_w : puissance mécanique demandée à la roue (W).
      *Peut être négative (régénération/frein moteur) si ton modèle le gère.*
    - rendement_transmission : eta dans (0, 1]
    - pertes_fixes_w : pertes additionnelles (W) indépendantes du couple/vitesse
      (ex: consommation auxiliaires mécaniques, pertes constantes estimées).
    - clamp_non_negative :
        True  -> si P_wheel + pertes_fixes < 0, retourne 0 (évite de demander une puissance moteur négative)
        False -> retourne une valeur négative (utile si tu modélises la régénération)

    Retour :
    - puissance moteur (W)
    """
    P_wheel = _require_finite("puissance_roue_w", puissance_roue_w)
    eta = _require_eta("rendement_transmission", rendement_transmission)
    P_losses = _require_finite("pertes_fixes_w", pertes_fixes_w)

    P_in = P_wheel + P_losses
    if clamp_non_negative and P_in < 0.0:
        return 0.0

    return P_in / eta


def calcul_couple_moteur(
    couple_roue_nm: float,
    rapport_reduction_global: float,
    rendement_transmission: float,
    *,
    couple_pertes_nm: float = 0.0,
    clamp_non_negative: bool = False,
) -> float:
    """
    Calcule le couple moteur requis à partir du couple à la roue.

    Modèle :
      T_motor = (T_wheel + T_pertes) / (G * eta)

    Paramètres :
    - couple_roue_nm : couple demandé à la roue (N·m). Peut être négatif (freinage / regen).
    - rapport_reduction_global : G (>0). Exemple : 10 signifie réduction 10:1 (moteur tourne 10x plus vite).
    - rendement_transmission : eta dans (0, 1]
    - couple_pertes_nm : couple additionnel pour modéliser des pertes (frottements équivalents)
      ramenées à la roue (ou directement en N·m avant division si tu l'emploies comme ici).
    - clamp_non_negative :
        True  -> borne le résultat à >= 0
        False -> conserve le signe (utile pour regen / freinage)

    Retour :
    - couple moteur (N·m)
    """
    T_wheel = _require_finite("couple_roue_nm", couple_roue_nm)
    G = _require_positive("rapport_reduction_global", rapport_reduction_global, strictly=True)
    eta = _require_eta("rendement_transmission", rendement_transmission)
    T_losses = _require_finite("couple_pertes_nm", couple_pertes_nm)

    denom = G * eta
    if denom <= 0.0 or not math.isfinite(denom):
        raise ValueError("Dénominateur non valide (G*eta). Vérifie rapport et rendement.")

    T_motor = (T_wheel + T_losses) / denom
    return max(0.0, T_motor) if clamp_non_negative else T_motor
