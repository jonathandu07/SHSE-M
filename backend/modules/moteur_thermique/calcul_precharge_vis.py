def calcul_force_separation(pression_max_pa: float, aire_effective_m2: float) -> float:
    """
    Calcule la force de séparation exercée sur le couvercle.
    
    Formule : F_sep = p_max * A_eff
    """
    return pression_max_pa * aire_effective_m2

def calcul_precharge_vis_totale(force_separation_n: float, force_joint_n: float, facteur_securite: float = 1.5) -> float:
    """
    Calcule la précharge totale requise pour les vis.
    
    Formule : F_pre_tot >= gamma * F_sep + F_gasket
    """
    return (facteur_securite * force_separation_n) + force_joint_n

def calcul_couple_serrage(force_precharge_vis_n: float, diametre_nominal_m: float, facteur_frottement_k: float = 0.2) -> float:
    """
    Estime le couple de serrage nécessaire.
    
    Formule : M = K * F * d
    """
    return facteur_frottement_k * force_precharge_vis_n * diametre_nominal_m
