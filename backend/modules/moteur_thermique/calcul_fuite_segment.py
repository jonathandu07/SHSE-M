import math

def calcul_debit_fuite_annulaire(delta_p_pa: float, jeu_radial_h_m: float, rayon_m: float, longueur_fuite_l_m: float, viscosite_dynamique_pa_s: float) -> float:
    """
    Calcule le débit de fuite volumique dans un jeu annulaire (Laminaire, Poiseuille).
    
    Formule : Q = (pi * r * h^3 * Delta_P) / (6 * mu * L)
    """
    if longueur_fuite_l_m <= 0 or viscosite_dynamique_pa_s <= 0:
        raise ValueError("Longueur et viscosité doivent être positives.")
        
    numerateur = math.pi * rayon_m * (jeu_radial_h_m**3) * delta_p_pa
    denominateur = 6 * viscosite_dynamique_pa_s * longueur_fuite_l_m
    
    return numerateur / denominateur

def calcul_masse_fuite(debit_volumique_m3s: float, densite_kg_m3: float) -> float:
    """
    Calcule le débit massique de fuite.
    """
    return debit_volumique_m3s * densite_kg_m3
