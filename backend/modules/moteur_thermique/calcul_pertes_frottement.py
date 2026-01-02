def calcul_puissance_frottement_segment(force_normale_n: float, vitesse_moyenne_ms: float, coef_frottement: float) -> float:
    """
    Estime la puissance dissipée par frottement d'un segment ou joint.
    
    Formule : P_f = mu * N * v
    """
    return coef_frottement * force_normale_n * vitesse_moyenne_ms

def calcul_puissance_frottement_palier(charge_w: float, vitesse_glissement_ms: float, coef_frottement_f: float) -> float:
    """
    Estime la puissance dissipée dans un palier lisse.
    
    Formule : P_f = f * W * v
    """
    return coef_frottement_f * charge_w * vitesse_glissement_ms
