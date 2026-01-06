# backend\modules\alternateur\calcul_vitesse_angulaire.py
from __future__ import annotations

import math
from typing import Literal


def calcul_vitesse_angulaire(
    vitesse_rotation_tr_min: float,
    *,
    # Permet de garder un module utilisable dans des modèles où le signe encode le sens de rotation
    allow_negative: bool = True,
    # Si True, retourne |omega| (utile si tu veux uniquement une magnitude)
    clamp_non_negative: bool = False,
    # Conversion optionnelle si l'entrée est déjà en rad/s (évite doublons dans des pipelines)
    input_unite: Literal["rpm", "rad_s"] = "rpm",
) -> float:
    """
    Calcule la vitesse angulaire ω (rad/s).

    Formules :
      - si input_unite="rpm"   : ω = (2π * n_rpm) / 60
      - si input_unite="rad_s" : ω = n (identité)

    Paramètres
    ----------
    vitesse_rotation_tr_min : float
        Vitesse de rotation.
        - En rpm si input_unite="rpm" (défaut)
        - En rad/s si input_unite="rad_s"
        Le signe peut représenter un sens de rotation si allow_negative=True.
    allow_negative : bool
        - True (défaut)  : autorise les rpm négatifs (sens de rotation)
        - False          : lève une erreur si la valeur est négative
    clamp_non_negative : bool
        - True  : retourne |ω|
        - False : conserve le signe
    input_unite : {"rpm","rad_s"}
        Unité d'entrée.

    Retour
    ------
    float
        Vitesse angulaire ω (rad/s).

    Exceptions
    ----------
    ValueError
        Si l'entrée n'est pas finie (NaN/inf) ou si négatif interdit.
    """
    # -----------------------------
    # Validation robuste (sans rigidifier inutilement)
    # -----------------------------
    if not isinstance(vitesse_rotation_tr_min, (int, float)) or not math.isfinite(vitesse_rotation_tr_min):
        raise ValueError(
            f"vitesse_rotation_tr_min doit être un nombre fini (reçu: {vitesse_rotation_tr_min!r})."
        )

    x = float(vitesse_rotation_tr_min)

    if not allow_negative and x < 0.0:
        raise ValueError("La vitesse de rotation ne peut pas être négative (allow_negative=False).")

    # -----------------------------
    # Conversion
    # -----------------------------
    if input_unite == "rpm":
        omega = (2.0 * math.pi * x) / 60.0
    elif input_unite == "rad_s":
        omega = x
    else:
        raise ValueError("input_unite doit être 'rpm' ou 'rad_s'.")

    if clamp_non_negative:
        omega = abs(omega)

    return omega
