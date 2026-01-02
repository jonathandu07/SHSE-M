import math

def calcul_cylindree_unitaire(alesage_m: float, course_m: float) -> float:
    """
    Calcule la cylindrée unitaire.
    
    Formule : V_d = (pi * B^2 / 4) * S
    """
    return (math.pi * (alesage_m**2) / 4.0) * course_m

def calcul_cylindree_totale(cylindree_unitaire_m3: float, nombre_cylindres: int) -> float:
    """
    Calcule la cylindrée totale.
    """
    return cylindree_unitaire_m3 * nombre_cylindres
