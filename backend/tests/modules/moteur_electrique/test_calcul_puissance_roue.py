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


def calcul_puissance_roue(
    force_requise_n: float,
    vitesse_ms: float,
    *,
    use_abs_speed: bool = False,
    clamp_non_negative: bool = False,
) -> float:
    """
    Calcule la puissance mécanique aux roues.

    Formule :
      P_wheel = F_req * v

    Paramètres :
    - force_requise_n : force longitudinale requise (N).
      Convention typique : positive = traction demandée, négative = freinage / régénération.
    - vitesse_ms : vitesse (m/s). Peut être négative si ton repère le permet.
    - use_abs_speed :
        True  -> utilise |v| (utile si tu stockes v négative mais que tu veux une puissance "scalaire")
        False -> conserve le signe (puissance négative possible en regen).
    - clamp_non_negative :
        True  -> borne P >= 0 (si tu ne veux pas de regen dans ce niveau de modèle)
        False -> conserve le signe.

    Retour :
    - puissance roue (W)
    """
    F = _require_finite("force_requise_n", force_requise_n)
    v = _require_finite("vitesse_ms", vitesse_ms)

    v_eff = abs(v) if use_abs_speed else v
    P = F * v_eff
    return max(0.0, P) if clamp_non_negative else P


def calcul_couple_roue_total(
    force_requise_n: float,
    rayon_roue_m: float,
    *,
    clamp_non_negative: bool = False,
) -> float:
    """
    Calcule le couple total nécessaire aux roues.

    Formule :
      T_wheel_total = F_req * R

    Paramètres :
    - force_requise_n : force longitudinale requise (N).
      (positive traction, négative freinage / regen)
    - rayon_roue_m : rayon dynamique de roue (m) (>0)
    - clamp_non_negative :
        True  -> borne T >= 0
        False -> conserve le signe.

    Retour :
    - couple total aux roues (N·m)
    """
    F = _require_finite("force_requise_n", force_requise_n)
    R = _require_positive("rayon_roue_m", rayon_roue_m, strictly=True)

    T = F * R
    return max(0.0, T) if clamp_non_negative else T


def calcul_couple_par_roue(
    couple_roue_total_nm: float,
    nb_roues_motrices: int,
    *,
    repartition: Literal["egal", "avant", "arriere"] = "egal",
) -> float:
    """
    Répartit un couple total entre plusieurs roues motrices.

    Paramètres :
    - couple_roue_total_nm : couple total demandé aux roues (N·m)
    - nb_roues_motrices : nombre de roues motrices (>=1)
    - repartition :
        'egal'   -> partage uniforme (défaut)
        'avant'  -> placeholder sémantique (identique à 'egal' ici, utile si tu étends plus tard)
        'arriere'-> placeholder sémantique

    Retour :
    - couple par roue (N·m)
    """
    Ttot = _require_finite("couple_roue_total_nm", couple_roue_total_nm)
    if not isinstance(nb_roues_motrices, int) or nb_roues_motrices < 1:
        raise ValueError("nb_roues_motrices doit être un entier >= 1.")

    _ = repartition  # conservé pour compatibilité/extension future
    return Ttot / nb_roues_motrices
