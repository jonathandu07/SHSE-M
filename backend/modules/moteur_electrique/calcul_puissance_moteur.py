def calcul_puissance_moteur_electrique(puissance_roue_w: float, rendement_transmission: float) -> float:
    """
    Calcule la puissance moteur nécessaire en tenant compte du rendement de transmission.

    Formule : P_motor = P_wheel / eta_trans
    """
    if rendement_transmission <= 0 or rendement_transmission > 1:
        raise ValueError("Le rendement doit être entre 0 et 1.")
        
    return puissance_roue_w / rendement_transmission

def calcul_couple_moteur(couple_roue_nm: float, rapport_reduction_global: float, rendement_transmission: float) -> float:
    """
    Calcule le couple moteur requis.

    Formule : T_motor = T_wheel / (G * eta)
    """
    return couple_roue_nm / (rapport_reduction_global * rendement_transmission)
