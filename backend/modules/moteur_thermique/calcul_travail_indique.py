def calcul_travail_indique_pme(pression_moyenne_effective_pa: float, cylindree_m3: float) -> float:
    """
    Calcule le travail indiqué par cycle (W_i).
    
    Formule : W_i = PME * V_d
    """
    return pression_moyenne_effective_pa * cylindree_m3

def calcul_puissance_indiquee(travail_indique_j: float, vitesse_rotation_tr_min: float, temps_moteur: int = 4) -> float:
    """
    Calcule la puissance indiquée (P_i).
    
    Args:
        temps_moteur (int): 2 pour 2-temps, 4 pour 4-temps.
    """
    if temps_moteur not in [2, 4]:
        raise ValueError("Le cycle doit être 2 temps ou 4 temps.")
        
    cycles_par_seconde = vitesse_rotation_tr_min / 60.0
    if temps_moteur == 4:
        cycles_par_seconde /= 2.0
        
    return travail_indique_j * cycles_par_seconde
