import math

def calcul_force_gaz(pression_pa: float, alesage_m: float) -> float:
    """
    Calcule la force exercée par les gaz sur le piston.

    Formule : F_g = p * A_p
    avec A_p = pi * B^2 / 4
    """
    acces_piston = (math.pi * (alesage_m**2)) / 4.0
    return pression_pa * acces_piston
