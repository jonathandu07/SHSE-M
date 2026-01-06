# backend\modules\moteur_thermique\calcul_couple_vilebrequin.py
from __future__ import annotations

import math
from typing import Literal


def _is_finite(x: float) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def _require_finite(name: str, x: float) -> float:
    if not _is_finite(x):
        raise ValueError(f"{name} doit être un nombre fini (reçu: {x!r}).")
    return float(x)


def _require_non_negative(name: str, x: float) -> float:
    x = _require_finite(name, x)
    if x < 0.0:
        raise ValueError(f"{name} doit être >= 0 (reçu: {x}).")
    return x


def calcul_couple_instantane(
    force_bielle_n: float,
    rayon_manivelle_m: float,
    angle_vilebrequin_deg: float,
    *,
    # Options sans casser l'appel existant
    angle_unite: Literal["deg", "rad"] = "deg",
    use_abs_rayon: bool = True,
    clamp_non_negative: bool = False,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule le couple instantané sur le vilebrequin (modèle simplifié).

    Modèle de base (inchangé) :
      T ≈ F_bielle * r * sin(θ)

    Hypothèses :
    - bras de levier pris comme r * sin(θ) (pas de correction d'obliquité de bielle)
    - la force "force_bielle_n" est une force effective transmise (ex: F_gaz - F_inertie)

    Paramètres :
    - force_bielle_n : force sur bielle (N). Peut être signée selon la convention (compression/traction).
    - rayon_manivelle_m : rayon de manivelle r (m). Physiquement >= 0.
    - angle_vilebrequin_deg : angle θ (en degrés par défaut)
    - angle_unite : "deg" (défaut) ou "rad"
    - use_abs_rayon : True (défaut) -> utilise |r| (évite un signe parasite si r est donné négatif)
    - clamp_non_negative : True -> borne le couple à >= 0 (si tu veux une magnitude)
    - return_details : True -> renvoie aussi sin(θ) et valeurs intermédiaires

    Retour :
    - couple instantané T (N·m) ou dict si return_details=True
    """
    F = _require_finite("force_bielle_n", force_bielle_n)
    r = _require_finite("rayon_manivelle_m", rayon_manivelle_m)
    theta_in = _require_finite("angle_vilebrequin_deg", angle_vilebrequin_deg)

    # Rayon: on garde module-friendly (pas d'interdiction brutale),
    # mais par défaut on prend la valeur absolue car un rayon négatif n'a pas de sens physique.
    r_eff = abs(r) if use_abs_rayon else r

    # Conversion angle
    if angle_unite == "deg":
        theta = math.radians(theta_in)
    elif angle_unite == "rad":
        theta = theta_in
    else:
        raise ValueError("angle_unite doit être 'deg' ou 'rad'.")

    sin_theta = math.sin(theta)
    T = F * r_eff * sin_theta

    if clamp_non_negative:
        T = max(0.0, T)

    if return_details:
        return {
            "T": T,
            "F": F,
            "r": r_eff,
            "theta_rad": theta,
            "sin_theta": sin_theta,
        }
    return T
