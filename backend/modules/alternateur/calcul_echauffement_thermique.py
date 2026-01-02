def calcul_echauffement_thermique(puissance_pertes_totale: float, resistance_thermique: float) -> float:
    """
    Calcule l'élévation de température (Delta T) basée sur les pertes et la résistance thermique.

    Formule : Delta T = R_theta * P_loss

    Args:
        puissance_pertes_totale (float): Puissance totale dissipée en chaleur (P_loss) en Watts.
        resistance_thermique (float): Résistance thermique globale (R_theta) en K/W (ou °C/W).

    Returns:
        float: Élévation de température en Kelvin (ou °C).
    """
    return resistance_thermique * puissance_pertes_totale
