import math

def calcul_contrainte_cisaillement_torsion(couple_nm: float, diametre_arbre_m: float) -> float:
    """
    Calcule la contrainte de cisaillement due à la torsion.

    Formule : tau_max = (16 * T) / (pi * d^3)

    Args:
        couple_nm (float): Couple (T) en N.m.
        diametre_arbre_m (float): Diamètre de l'arbre (d) en mètres.

    Returns:
        float: Contrainte de cisaillement (tau) en Pa.
    """
    return (16 * couple_nm) / (math.pi * (diametre_arbre_m**3))

def calcul_contrainte_flexion_arbre(moment_flechissant_nm: float, diametre_arbre_m: float) -> float:
    """
    Calcule la contrainte normale due à la flexion.

    Formule : sigma_b = (32 * M) / (pi * d^3)
    """
    return (32 * moment_flechissant_nm) / (math.pi * (diametre_arbre_m**3))

def calcul_von_mises_arbre(contrainte_flexion: float, contrainte_cisaillement: float) -> float:
    """
    Calcule la contrainte équivalente de Von Mises.

    Formule : sigma_eq = sqrt(sigma_b^2 + 3 * tau^2)
    """
    return math.sqrt(contrainte_flexion**2 + 3 * contrainte_cisaillement**2)
