# backend\modules\alternateur\calcul_frequence_synchrone.py
from __future__ import annotations

import math
from typing import Literal


def calcul_frequence_synchrone(
    vitesse_rotation_tr_min: float,
    nombre_poles: int,
    *,
    mode_poles: Literal["poles", "pair_poles", "pole_pairs"] = "poles",
    clamp_non_negative: bool = True,
) -> float:
    """
    Calcule la fréquence électrique synchrone (machine synchrone).

    Formules (équivalentes selon la convention) :
      - si on fournit le nombre de pôles P :
          f = n_rpm * P / 120
      - si on fournit le nombre de paires de pôles p (= P/2) :
          f = n_rpm * p / 60

    Paramètres :
    - vitesse_rotation_tr_min : vitesse mécanique n (tr/min). Peut être négative si tu représentes un sens
      de rotation ; clamp_non_negative permet de retourner une fréquence >= 0.
    - nombre_poles :
        * mode_poles="poles" ou "pair_poles" : nombre de pôles P (entier pair >0)
        * mode_poles="pole_pairs"           : nombre de paires de pôles p (entier >0)
    - mode_poles :
        - "poles"      : interprète nombre_poles comme P (pôles)
        - "pair_poles" : alias de "poles" (garde compatibilité sémantique)
        - "pole_pairs" : interprète nombre_poles comme p (paires de pôles)
    - clamp_non_negative :
        True  -> retourne |f|
        False -> conserve le signe (utile si tu veux garder la convention de sens)

    Retour :
    - fréquence électrique f (Hz)
    """
    # Validations "musclées" mais sans rigidifier inutilement
    if not isinstance(vitesse_rotation_tr_min, (int, float)) or not math.isfinite(vitesse_rotation_tr_min):
        raise ValueError(
            f"vitesse_rotation_tr_min doit être un nombre fini (reçu: {vitesse_rotation_tr_min!r})."
        )
    if not isinstance(nombre_poles, int):
        raise ValueError(f"nombre_poles doit être un entier (reçu: {nombre_poles!r}).")
    if nombre_poles <= 0:
        raise ValueError("nombre_poles doit être > 0.")

    n_rpm = float(vitesse_rotation_tr_min)

    mp = mode_poles.strip().lower()
    if mp in ("poles", "pair_poles"):
        P = nombre_poles
        if P % 2 != 0:
            raise ValueError("Le nombre de pôles (P) doit être un entier pair positif.")
        f = (n_rpm * P) / 120.0
    elif mp == "pole_pairs":
        p = nombre_poles  # paires de pôles
        f = (n_rpm * p) / 60.0
    else:
        raise ValueError("mode_poles doit être 'poles', 'pair_poles' ou 'pole_pairs'.")

    return abs(f) if clamp_non_negative else f
