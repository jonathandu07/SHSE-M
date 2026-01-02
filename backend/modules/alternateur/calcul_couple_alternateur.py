import math

def calcul_couple_alternateur(puissance_electrique_cible: float, rendement_alternateur: float, vitesse_angulaire: float) -> float:
    """
    Calcule le couple mécanique nécessaire pour fournir la puissance électrique cible.

    Formule : T_alt = P_e / (eta_alt * omega)

    Args:
        puissance_electrique_cible (float): Puissance électrique requise (P_e) en Watts (W).
        rendement_alternateur (float): Rendement de l'alternateur (eta_alt) entre 0 et 1.
        vitesse_angulaire (float): Vitesse angulaire (omega) en radians par seconde (rad/s).

    Returns:
        float: Couple nécessaire en Newton-mètres (N.m).
    """
    if vitesse_angulaire == 0:
        raise ValueError("La vitesse angulaire ne peut pas être nulle.")
    if rendement_alternateur <= 0 or rendement_alternateur > 1:
        raise ValueError("Le rendement doit être compris entre 0 (exclu) et 1.")
        
    puissance_mec = puissance_electrique_cible / rendement_alternateur
    couple = puissance_mec / vitesse_angulaire
    return couple
