def calcul_puissance_roue(force_requise_n: float, vitesse_ms: float) -> float:
    """
    Calcule la puissance mécanique nécessaire aux roues.

    Formule : P_wheel = F_req * v
    """
    return force_requise_n * vitesse_ms

def calcul_couple_roue_total(force_requise_n: float, rayon_roue_m: float) -> float:
    """
    Calcule le couple total nécessaire aux roues.
    
    Formule : T_wheel = F_req * R
    """
    return force_requise_n * rayon_roue_m
