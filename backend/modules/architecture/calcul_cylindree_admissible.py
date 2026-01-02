import math

def calcul_bore_max_admissible(vitesse_piston_max_ms: float, regime_tr_min: float, ratio_course_alesage_max: float) -> float:
    """
    Calcule l'alésage maximal admissible pour ne pas dépasser la vitesse piston critique.
    
    Formule : B_star = min(B_limit, S_max / r_max)
              avec S_max = 30 * Up_max / n
    
    Args:
        vitesse_piston_max_ms (float): Vitesse moyenne piston limite (ex: 25 m/s).
        regime_tr_min (float): Régime nominal (n).
        ratio_course_alesage_max (float): Ratio S/B max géométrique.
        
    Returns:
        float: Alésage maximal (B*) en mètres.
    """
    if regime_tr_min == 0: return 0.0
    
    course_max_physique = (30.0 * vitesse_piston_max_ms) / regime_tr_min
    
    # B <= S / r
    bore_max_dyn = course_max_physique / ratio_course_alesage_max
    
    return bore_max_dyn

def calcul_cylindree_unit_max(bore_max_m: float, ratio_course_alesage_max: float) -> float:
    """
    Calcule la cylindrée unitaire maximale dérivée.
    
    Formule : V_cyl_max = (pi * B_max^3 * r_max) / 4
    """
    return (math.pi / 4) * (bore_max_m ** 3) * ratio_course_alesage_max
