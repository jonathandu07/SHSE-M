import math

def calcul_vitesse_angulaire(vitesse_rotation_tr_min: float) -> float:
    """
    Calcule la vitesse angulaire (oméga) en radians par seconde.

    Formule : omega = (2 * pi * n) / 60

    Args:
        vitesse_rotation_tr_min (float): Vitesse de rotation (n) en tours par minute (tr/min).

    Returns:
        float: Vitesse angulaire en radians par seconde (rad/s).
    """
    if vitesse_rotation_tr_min < 0:
        raise ValueError("La vitesse de rotation ne peut pas être négative.")
        
    omega = (2 * math.pi * vitesse_rotation_tr_min) / 60
    return omega
