# backend\modules\alternateur\calcul_rendement_alternateur.py
from __future__ import annotations

import math
from typing import Iterable, Optional


def calcul_rendement_alternateur(
    puissance_utile_out: float,
    somme_pertes: float = 0,
    liste_pertes: Optional[Iterable[float]] = None,
    *,
    # Comportements optionnels (défaut = compatibilité "module")
    clamp_0_1: bool = True,
    ignore_none_in_list: bool = True,
    reject_negative_losses: bool = False,
    epsilon: float = 1e-12,
    return_details: bool = False,
) -> float | dict[str, float]:
    """
    Calcule le rendement de l'alternateur.

    Formule :
        eta = P_out / (P_out + Pertes)

    Paramètres
    ----------
    puissance_utile_out : float
        Puissance électrique utile en sortie P_out (W).
        Généralement >= 0. (On ne bloque pas strictement pour rester opérable.)
    somme_pertes : float, optionnel
        Somme globale des pertes (W). Utilisée si liste_pertes n'est pas fournie.
        Défaut = 0.
    liste_pertes : iterable[float] | None, optionnel
        Liste des pertes individuelles (W). Si fournie (même vide), elle est utilisée
        en priorité sur somme_pertes, comme dans ton intention initiale.

    Options (pour fiabiliser sans casser l’usage)
    --------------------------------------------
    clamp_0_1 : bool
        Si True (défaut), borne le résultat dans [0, 1] (évite les dépassements numériques).
    ignore_none_in_list : bool
        Si True (défaut), ignore les éléments None dans liste_pertes.
    reject_negative_losses : bool
        Si True, lève une erreur si une perte < 0 est détectée (sécurité).
        Si False (défaut), on accepte des pertes négatives (cas rare mais possible si "crédit" ou
        convention de signe dans un pipeline).
    epsilon : float
        Seuil anti-division par 0 (défaut 1e-12). Si P_in <= epsilon, renvoie 0.0.
    return_details : bool
        Si True, renvoie un dict avec P_out, P_losses, P_in, eta.

    Retour
    ------
    float (ou dict si return_details=True)
        Rendement eta (0..1 typiquement).
    """
    # -----------------------------
    # Validation légère mais robuste (NaN/inf)
    # -----------------------------
    if not isinstance(puissance_utile_out, (int, float)) or not math.isfinite(puissance_utile_out):
        raise ValueError(
            f"puissance_utile_out doit être un nombre fini (reçu: {puissance_utile_out!r})."
        )
    if not isinstance(somme_pertes, (int, float)) or not math.isfinite(somme_pertes):
        raise ValueError(f"somme_pertes doit être un nombre fini (reçu: {somme_pertes!r}).")
    if not isinstance(epsilon, (int, float)) or not math.isfinite(epsilon) or float(epsilon) < 0.0:
        raise ValueError("epsilon doit être un nombre fini >= 0.")

    P_out = float(puissance_utile_out)

    # -----------------------------
    # Calcul des pertes totales
    # - Compatibilité : si liste_pertes est fournie et non vide -> somme(liste)
    # - Amélioration : si liste_pertes est fournie mais vide -> pertes = 0 (au lieu de retomber sur somme_pertes)
    #   (ça évite un comportement ambigu)
    # -----------------------------
    if liste_pertes is not None:
        total = 0.0
        for i, x in enumerate(liste_pertes):
            if x is None and ignore_none_in_list:
                continue
            if not isinstance(x, (int, float)) or not math.isfinite(x):
                raise ValueError(f"liste_pertes[{i}] doit être un nombre fini (reçu: {x!r}).")
            if reject_negative_losses and float(x) < 0.0:
                raise ValueError(f"liste_pertes[{i}] est négative ({float(x)} W), incohérent si pertes.")
            total += float(x)
        P_losses = total
    else:
        P_losses = float(somme_pertes)
        if reject_negative_losses and P_losses < 0.0:
            raise ValueError("somme_pertes est négative, incohérent si pertes.")

    # Puissance entrée
    P_in = P_out + P_losses

    # Anti-division par 0 / cas dégénéré
    if P_in <= float(epsilon):
        eta = 0.0
    else:
        eta = P_out / P_in

    # Borne optionnelle (utile contre erreurs d'arrondi ou entrées atypiques)
    if clamp_0_1:
        eta = max(0.0, min(1.0, eta))

    if return_details:
        return {"eta": eta, "P_out": P_out, "P_losses": P_losses, "P_in": P_in}
    return eta
