def calcul_volume_usure_archard(coefficient_usure_k: float, charge_normale_w: float, distance_glissement_ls: float, durete_h: float) -> float:
    """
    Calcule le volume de matière usée.
    
    Formule : V_w = k * (W * Ls) / H
    
    Args:
        coefficient_usure_k (float): Coefficient adimensionnel (ex: 1e-4 à 1e-8).
        charge_normale_w (float): Charge normale (N).
        distance_glissement_ls (float): Distance totale parcourue (m).
        durete_h (float): Dureté du matériau le plus tendre (Pa, attention aux unités souvent en Vickers/Brinell à convertir).
    
    Returns:
        float: Volume usé (m3).
    """
    if durete_h <= 0:
        raise ValueError("La dureté doit être positive.")
        
    return coefficient_usure_k * (charge_normale_w * distance_glissement_ls) / durete_h

def calcul_perte_epaisseur(volume_use_m3: float, aire_contact_m2: float) -> float:
    """
    Calcule la perte d'épaisseur moyenne.
    
    Formule : delta_h = V_w / A
    """
    if aire_contact_m2 <= 0:
        raise ValueError("Aire de contact positive requise.")
    return volume_use_m3 / aire_contact_m2
