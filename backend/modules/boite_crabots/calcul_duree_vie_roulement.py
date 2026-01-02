def calcul_charge_equivalente_roulement(force_radiale: float, force_axiale: float, facteur_x: float, facteur_y: float) -> float:
    """
    Calcule la charge dynamique équivalente.

    Formule : P = X * F_r + Y * F_a
    """
    return facteur_x * force_radiale + facteur_y * force_axiale

def calcul_duree_vie_l10(charge_dynamique_base_c: float, charge_equivalente_p: float, type_roulement: str = 'bille') -> float:
    """
    Calcule la durée de vie L10 en millions de tours.

    Formule : L10 = (C / P)^p
    p = 3 pour billes, 10/3 pour rouleaux.
    """
    if type_roulement == 'bille':
        p = 3
    elif type_roulement == 'rouleau':
        p = 10/3
    else:
        raise ValueError("Type de roulement inconnu (utiliser 'bille' ou 'rouleau').")
    
    if charge_equivalente_p <= 0:
         return float('inf') # Charge nulle -> vie infinie (théorique)

    return (charge_dynamique_base_c / charge_equivalente_p) ** p

def calcul_duree_vie_heures(l10_millions: float, vitesse_rotation_tr_min: float) -> float:
    """
    Convertit L10 (millions de tours) en heures.

    Formule : L10h = (10^6 * L10) / (60 * n)
    """
    if vitesse_rotation_tr_min <= 0:
        raise ValueError("Vitesse doit être positive.")
        
    return (1000000 * l10_millions) / (60 * vitesse_rotation_tr_min)
