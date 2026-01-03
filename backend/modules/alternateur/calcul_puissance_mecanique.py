# backend\modules\alternateur\calcul_puissance_mecanique.py
from __future__ import annotations

import math
from typing import Literal


def calcul_puissance_mecanique(
    puissance_electrique_cible: float,
    rendement_alternateur: float,
    *,
    pertes_fixes_w: float = 0.0,
    clamp_non_negative: bool = False,
    mode_signe: Literal["conserver", "abs"] = "conserver",
) -> float:
    """
    Calcule la puissance mécanique requise à l'arbre pour obtenir une puissance électrique cible.

    Modèle de base (inchangé) :
        P_mec = P_e / eta_alt

    Extension optionnelle (plus réaliste) :
        P_mec = (P_e + P_pertes_fixes) / eta_alt

    Paramètres
    ----------
    puissance_electrique_cible : float
        Puissance électrique requise P_e (W).
        Peut être négative si ton modèle gère la régénération (convention de signe).
    rendement_alternateur : float
        Rendement de l'alternateur eta_alt dans (0, 1].
    pertes_fixes_w : float, optionnel
        Pertes fixes additionnelles (W) (ex: pertes excitation, frottements équivalents en W).
        Défaut = 0.0 pour conserver le comportement historique.
    clamp_non_negative : bool, optionnel
        Si True, borne P_mec à >= 0 (utile si tu ne veux pas de puissance mécanique négative).
        Défaut = False (conserve la compatibilité avec des modèles signés).
    mode_signe : {"conserver","abs"}, optionnel
        - "conserver" : conserve le signe (P_mec suit le signe de (P_e + pertes))
        - "abs"       : retourne |P_mec| (puissance mécanique en valeur)
        Défaut = "conserver"

    Returns
    -------
    float
        Puissance mécanique requise (W).

    Exceptions
    ----------
    ValueError
        Si les entrées ne sont pas finies (NaN/inf) ou si le rendement n'est pas dans (0,1].
    """
    # -----------------------------
    # Validations "musclées" mais module-friendly
    # -----------------------------
    if not isinstance(puissance_electrique_cible, (int, float)) or not math.isfinite(puissance_electrique_cible):
        raise ValueError(
            f"puissance_electrique_cible doit être un nombre fini (reçu: {puissance_electrique_cible!r})."
        )

    if not isinstance(rendement_alternateur, (int, float)) or not math.isfinite(rendement_alternateur):
        raise ValueError(
            f"rendement_alternateur doit être un nombre fini (reçu: {rendement_alternateur!r})."
        )

    eta = float(rendement_alternateur)
    if not (0.0 < eta <= 1.0):
        raise ValueError("Le rendement doit être compris dans (0, 1].")

    if not isinstance(pertes_fixes_w, (int, float)) or not math.isfinite(pertes_fixes_w):
        raise ValueError(f"pertes_fixes_w doit être un nombre fini (reçu: {pertes_fixes_w!r}).")

    # -----------------------------
    # Calcul
    # -----------------------------
    P_e = float(puissance_electrique_cible)
    P_losses = float(pertes_fixes_w)

    # Puissance mécanique requise (avec pertes fixes optionnelles)
    P_mec = (P_e + P_losses) / eta

    # Gestion optionnelle du signe
    if mode_signe == "abs":
        P_mec = abs(P_mec)
    elif mode_signe != "conserver":
        raise ValueError("mode_signe doit être 'conserver' ou 'abs'.")

    # Option de sécurité
    if clamp_non_negative:
        P_mec = max(0.0, P_mec)

    return P_mec
