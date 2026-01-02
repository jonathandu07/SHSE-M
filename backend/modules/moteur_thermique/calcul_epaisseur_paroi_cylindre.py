import math

def calcul_epaisseur_cylindre_mince(pression_pa: float, rayon_interne_m: float, contrainte_admissible_pa: float) -> float:
    """
    Calcule l'épaisseur minimale pour un cylindre mince.

    Formule : t >= (p * r_i) / sigma_adm
    """
    if contrainte_admissible_pa <= 0:
        raise ValueError("La contrainte admissible doit être positive.")
        
    return (pression_pa * rayon_interne_m) / contrainte_admissible_pa

def calcul_epaisseur_cylindre_lame(pression_interne_pa: float, rayon_interne_m: float, contrainte_admissible_pa: float) -> float:
    """
    Calcule l'épaisseur (via le rayon externe) pour un cylindre épais (Formule de Lamé).

    On cherche r_o tel que la contrainte circonférentielle max en r_i soit <= sigma_adm.
    sigma_theta(ri) = p * (ro^2 + ri^2) / (ro^2 - ri^2)
    """
    # Inversion de la formule :
    # sigma_adm * (ro^2 - ri^2) = p * (ro^2 + ri^2)
    # sigma_adm * ro^2 - sigma_adm * ri^2 = p * ro^2 + p * ri^2
    # ro^2 * (sigma_adm - p) = ri^2 * (sigma_adm + p)
    # ro = ri * sqrt( (sigma_adm + p) / (sigma_adm - p) )
    
    if contrainte_admissible_pa <= pression_interne_pa:
        raise ValueError("La contrainte admissible doit être supérieure à la pression interne pour un dimensionnement statique simple.")
        
    rayon_externe = rayon_interne_m * math.sqrt((contrainte_admissible_pa + pression_interne_pa) / (contrainte_admissible_pa - pression_interne_pa))
    return rayon_externe - rayon_interne_m
