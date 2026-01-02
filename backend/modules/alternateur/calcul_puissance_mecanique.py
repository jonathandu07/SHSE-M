def calcul_puissance_mecanique(puissance_electrique_cible: float, rendement_alternateur: float) -> float:
    """
    Calcule la puissance mécanique requise pour obtenir la puissance électrique cible.

    Formule : P_mec = P_e / eta_alt

    Args:
        puissance_electrique_cible (float): Puissance électrique requise (P_e) en Watts (W).
        rendement_alternateur (float): Rendement de l'alternateur (eta_alt) entre 0 et 1.

    Returns:
        float: Puissance mécanique en Watts (W).
    """
    if rendement_alternateur <= 0 or rendement_alternateur > 1:
        raise ValueError("Le rendement doit être compris entre 0 (exclu) et 1.")

    return puissance_electrique_cible / rendement_alternateur
