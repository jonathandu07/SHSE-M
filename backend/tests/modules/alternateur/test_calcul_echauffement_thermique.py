# backend\modules\alternateur\calcul_echauffement_thermique.py
from __future__ import annotations

import math


def calcul_echauffement_thermique(
    puissance_pertes_totale: float,
    resistance_thermique: float,
    *,
    offset_temperature: float = 0.0,
    clamp_non_negative: bool = False,
) -> float:
    """
    Calcule l'élévation de température (Delta T) basée sur les pertes et la résistance thermique.

    Modèle :
      DeltaT = R_theta * P_loss

    Paramètres :
    - puissance_pertes_totale : P_loss (W). Peut être négative si tu modélises un refroidissement net
      (rare) ou si une étape amont donne un signe.
    - resistance_thermique : R_theta (K/W ou °C/W). Typiquement >= 0.
    - offset_temperature : ajoute un offset à DeltaT (par défaut 0). Utile si tu veux retourner
      directement une température relative à une référence (ex: DeltaT + marge).
    - clamp_non_negative : True -> borne DeltaT à >= 0 (évite des sorties non physiques si P_loss < 0).

    Retour :
    - DeltaT (K ou °C)
    """
    # Validation légère (module-friendly) : seulement finitude + cas physiques usuels
    if not isinstance(puissance_pertes_totale, (int, float)) or not math.isfinite(puissance_pertes_totale):
        raise ValueError(
            f"puissance_pertes_totale doit être un nombre fini (reçu: {puissance_pertes_totale!r})."
        )
    if not isinstance(resistance_thermique, (int, float)) or not math.isfinite(resistance_thermique):
        raise ValueError(
            f"resistance_thermique doit être un nombre fini (reçu: {resistance_thermique!r})."
        )
    if not isinstance(offset_temperature, (int, float)) or not math.isfinite(offset_temperature):
        raise ValueError(
            f"offset_temperature doit être un nombre fini (reçu: {offset_temperature!r})."
        )

    Rth = float(resistance_thermique)
    Ploss = float(puissance_pertes_totale)

    # On autorise Rth négatif (cas très atypique) mais on protège l'utilisateur si besoin :
    # Si tu veux interdire: remplace par un raise si Rth < 0.
    delta_t = Rth * Ploss + float(offset_temperature)

    if clamp_non_negative:
        return max(0.0, delta_t)
    return delta_t
