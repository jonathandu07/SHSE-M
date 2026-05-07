# backend\modules\alternateur\calcul_couple_alternateur.py
from __future__ import annotations

import math
from typing import Literal, Optional


def calcul_couple_alternateur(
    puissance_electrique_cible: float,
    rendement_alternateur: float,
    vitesse_angulaire: float,
    *,
    pertes_fixes_w: float = 0.0,
    clamp_non_negative: bool = False,
    mode_signe: Literal["conserver", "abs_omega"] = "conserver",
    epsilon_omega: float = 1e-12,
) -> float:
    """
    Calcule le couple mécanique nécessaire pour fournir une puissance électrique cible.

    Modèle :
      P_mec = (P_elec + pertes_fixes_w) / eta_alt
      T_alt = P_mec / omega

    Paramètres :
    - puissance_electrique_cible : P_elec (W). Peut être négative si ton modèle gère la régénération.
    - rendement_alternateur      : eta_alt dans (0, 1]
    - vitesse_angulaire          : omega (rad/s). Peut être négative selon la convention de rotation.
    - pertes_fixes_w             : pertes additionnelles (W) indépendantes de la vitesse/couple (optionnel).
    - clamp_non_negative         : True -> borne le couple à >= 0 (sinon conserve le signe).
    - mode_signe :
        - "conserver" : conserve le signe de omega (et donc le signe final suit P/omega)
        - "abs_omega" : utilise |omega| (utile si tu veux un couple "magnitude" sans dépendre du sens)
    - epsilon_omega              : seuil anti-division par ~0 pour éviter instabilités numériques.

    Retour :
    - couple (N·m)
    """
    # Validations "musclées" mais non bloquantes pour les cas usuels
    if not isinstance(puissance_electrique_cible, (int, float)) or not math.isfinite(puissance_electrique_cible):
        raise ValueError(f"puissance_electrique_cible doit être un nombre fini (reçu: {puissance_electrique_cible!r}).")

    if not isinstance(rendement_alternateur, (int, float)) or not math.isfinite(rendement_alternateur):
        raise ValueError(f"rendement_alternateur doit être un nombre fini (reçu: {rendement_alternateur!r}).")
    if not (0.0 < float(rendement_alternateur) <= 1.0):
        raise ValueError("Le rendement doit être compris dans (0, 1].")

    if not isinstance(vitesse_angulaire, (int, float)) or not math.isfinite(vitesse_angulaire):
        raise ValueError(f"vitesse_angulaire doit être un nombre fini (reçu: {vitesse_angulaire!r}).")

    if not isinstance(pertes_fixes_w, (int, float)) or not math.isfinite(pertes_fixes_w):
        raise ValueError(f"pertes_fixes_w doit être un nombre fini (reçu: {pertes_fixes_w!r}).")

    if not isinstance(epsilon_omega, (int, float)) or not math.isfinite(epsilon_omega) or float(epsilon_omega) <= 0.0:
        raise ValueError("epsilon_omega doit être un nombre fini > 0.")

    omega = float(vitesse_angulaire)
    if abs(omega) <= float(epsilon_omega):
        raise ValueError("La vitesse angulaire ne peut pas être nulle (ou trop proche de 0).")

    eta = float(rendement_alternateur)
    P_e = float(puissance_electrique_cible)
    P_losses = float(pertes_fixes_w)

    # Puissance mécanique requise à l'arbre
    P_mec = (P_e + P_losses) / eta

    # Gestion du signe/du sens de rotation
    if mode_signe == "abs_omega":
        omega_eff = abs(omega)
    elif mode_signe == "conserver":
        omega_eff = omega
    else:
        raise ValueError("mode_signe doit être 'conserver' ou 'abs_omega'.")

    couple = P_mec / omega_eff
    return max(0.0, couple) if clamp_non_negative else couple
