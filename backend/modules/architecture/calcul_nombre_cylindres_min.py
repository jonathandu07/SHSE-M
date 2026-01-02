import math

def calcul_nombre_cylindres_min(cylindree_totale_m3: float, cylindree_unitaire_max_m3: float) -> int:
    """
    Calcule le nombre minimal de cylindres requis pour loger la cylindrée totale
    sans dépasser les limites unitaires (vitesse piston, alésage).
    
    Formule : N_cyl = ceil(V_tot / V_cyl_max)
    
    Args:
        cylindree_totale_m3 (float): V_tot requise.
        cylindree_unitaire_max_m3 (float): V_cyl_max admissible.
        
    Returns:
        int: Nombre de cylindres entier.
    """
    if cylindree_unitaire_max_m3 <= 0:
        return 999 # Valeur absurdement haute si V_u_max est invalide
        
    ratio = cylindree_totale_m3 / cylindree_unitaire_max_m3
    return math.ceil(ratio)
