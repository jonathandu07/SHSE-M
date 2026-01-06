# backend\modules\moteur_thermique\calcul_force_inertie.py
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


def calcul_force_inertie_alternative(
    masse_alternative_kg: float,
    rayon_manivelle_m: float,
    vitesse_rotation_tr_min: float,
    longueur_bielle_m: float,
    angle_vilebrequin_deg: float,
    *,
    # Options non intrusives : par défaut même équation, mais plus robuste/clair
    angle_unite: Literal["deg", "rad"] = "deg",
    input_vitesse: Literal["rpm", "rad_s"] = "rpm",
    clamp_ratio_r_sur_l: bool = False,
    max_ratio_r_sur_l: float = 0.5,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule la force d'inertie des masses alternatives (piston + axe + fraction de bielle),
    dans un modèle bielle-manivelle classique (développement au 2e harmonique).

    Formule (inchangée) :
      F_i = m_eq * r * ω² * ( cos(θ) + (r/l) * cos(2θ) )

    Conventions :
    - Le signe dépend de θ et des cosinus ; la force peut être positive ou négative selon la phase.
    - m_eq >= 0, r >= 0, l > 0.
    - θ = 0 au PMH (souvent PMH combustion selon la convention).

    Paramètres :
    - masse_alternative_kg : m_eq (kg) >= 0
    - rayon_manivelle_m : r (m) >= 0 (souvent course/2)
    - vitesse_rotation_tr_min : n en rpm (défaut) OU ω en rad/s si input_vitesse="rad_s"
    - longueur_bielle_m : l (m) > 0
    - angle_vilebrequin_deg : θ (deg par défaut)
    - angle_unite : "deg" (défaut) ou "rad"
    - input_vitesse : "rpm" (défaut) ou "rad_s"
    - clamp_ratio_r_sur_l :
        False (défaut) -> aucun clamp (comportement math pur)
        True -> borne r/l à max_ratio_r_sur_l (sécurité si données amont incohérentes)
    - max_ratio_r_sur_l : borne max si clamp activé (valeur indicative, r/l typique ~0.2..0.35)
    - return_details : True -> renvoie aussi ω, λ=r/l, termes trigonométriques

    Retour :
    - F_i (N) ou dict si return_details=True
    """
    m_eq = _require_positive("masse_alternative_kg", masse_alternative_kg, strictly=False)
    r = _require_positive("rayon_manivelle_m", rayon_manivelle_m, strictly=False)
    l = _require_positive("longueur_bielle_m", longueur_bielle_m, strictly=True)
    theta_in = _require_finite("angle_vilebrequin_deg", angle_vilebrequin_deg)

    # Vitesse angulaire ω
    v_in = _require_finite("vitesse_rotation_tr_min", vitesse_rotation_tr_min)
    if input_vitesse == "rpm":
        # rpm peut être négatif (sens de rotation) : ω garde le signe, mais ω² annule le signe.
        omega = (2.0 * math.pi * v_in) / 60.0
    elif input_vitesse == "rad_s":
        omega = v_in
    else:
        raise ValueError("input_vitesse doit être 'rpm' ou 'rad_s'.")

    # Angle θ
    if angle_unite == "deg":
        theta = math.radians(theta_in)
    elif angle_unite == "rad":
        theta = theta_in
    else:
        raise ValueError("angle_unite doit être 'deg' ou 'rad'.")

    # Ratio λ = r/l
    ratio_lambda = r / l
    if clamp_ratio_r_sur_l:
        max_ratio = _require_positive("max_ratio_r_sur_l", max_ratio_r_sur_l, strictly=True)
        ratio_lambda = max(-max_ratio, min(max_ratio, ratio_lambda))

    cos1 = math.cos(theta)
    cos2 = math.cos(2.0 * theta)

    terme_trigo = cos1 + (ratio_lambda * cos2)

    Fi = m_eq * r * (omega ** 2) * terme_trigo

    if return_details:
        return {
            "F_i": Fi,
            "m_eq": m_eq,
            "r": r,
            "l": l,
            "omega_rad_s": omega,
            "theta_rad": theta,
            "lambda_r_sur_l": ratio_lambda,
            "cos_theta": cos1,
            "cos_2theta": cos2,
            "terme_trigo": terme_trigo,
        }
    return Fi
