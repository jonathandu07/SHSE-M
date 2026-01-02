import math

def calcul_contrainte_contact_hertz(force_tangentielle: float, largeur_denture_b: float, diametre_primitif_moyen: float, coefficient_zh: float) -> float:
    """
    Estime la pression de contact (Pression de Hertz).

    Formule : sigma_H = Z_H * sqrt(F_t / (b * d_m))

    Args:
        force_tangentielle (float): Force tangentielle (F_t) en N.
        largeur_denture_b (float): Largeur de denture (b) en mètres.
        diametre_primitif_moyen (float): Diamètre primitif (d_m ou d1) en mètres.
        coefficient_zh (float): Facteur de matériau/géométrie (Z_H). Ex: ~2.5 pour acier/acier 20°.

    Returns:
        float: Contrainte de contact (sigma_H) en Pascals (Pa).
    """
    if largeur_denture_b <= 0 or diametre_primitif_moyen <= 0:
        raise ValueError("Dimensions invalides.")
        
    terme_sous_racine = force_tangentielle / (largeur_denture_b * diametre_primitif_moyen)
    return coefficient_zh * math.sqrt(terme_sous_racine)
