import math

def calcul_puissance_triphase(tension_composee: float, courant_ligne: float, facteur_puissance: float = 1.0) -> float:
    """
    Calcule la puissance active en triphasé.

    Formule : P = sqrt(3) * V_LL * I_L * cos(phi)

    Args:
        tension_composee (float): Tension entre phases (V_LL) en Volts (V).
        courant_ligne (float): Courant de ligne (I_L) en Ampères (A).
        facteur_puissance (float): Facteur de puissance (cos phi), par défaut 1.0.

    Returns:
        float: Puissance active en Watts (W).
    """
    return math.sqrt(3) * tension_composee * courant_ligne * facteur_puissance

def calcul_puissance_monophase(tension: float, courant: float, facteur_puissance: float = 1.0) -> float:
    """
    Calcule la puissance active en monophasé.
    
    Formule : P = V * I * cos(phi)
    """
    return tension * courant * facteur_puissance

def calcul_puissance_dc(tension_dc: float, courant_dc: float) -> float:
    """
    Calcule la puissance en courant continu (DC).
    
    Formule : P = V_DC * I_DC
    """
    return tension_dc * courant_dc
