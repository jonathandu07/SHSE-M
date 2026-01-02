def calcul_contrainte_flexion_lewis(force_tangentielle: float, largeur_denture_b: float, module_m: float, facteur_forme_y: float) -> float:
    """
    Estime la contrainte de flexion en pied de dent (formule de Lewis simplifiée).

    Formule : sigma_F = F_t / (b * m * Y)

    Args:
        force_tangentielle (float): Force tangentielle (F_t) en N.
        largeur_denture_b (float): Largeur de la dent (b) en mètres.
        module_m (float): Module de la dent (m) en mètres.
        facteur_forme_y (float): Facteur de forme de Lewis (Y), sans dimension (dépend du nb dents).

    Returns:
        float: Contrainte de flexion (sigma_F) en Pascals (Pa).
    """
    if largeur_denture_b <= 0 or module_m <= 0 or facteur_forme_y <= 0:
        raise ValueError("Les dimensions et facteurs doivent être positifs.")
        
    return force_tangentielle / (largeur_denture_b * module_m * facteur_forme_y)
