import math

def calcul_couple_instantane(force_bielle_n: float, rayon_manivelle_m: float, angle_vilebrequin_deg: float) -> float:
    """
    Calcule le couple instantané (simplifié, tangente pure sans obliquité bielle dans le bras de levier exact).
    
    Pour un modèle plus précis : T = F_tan * r
    avec force tangentielle dépendant de l'angle bielle.
    Ici, approximation simple donnée dans le doc : T approx F_rod * r * sin(theta)
    
    Args:
        force_bielle_n (float): Force transmise par la bielle (F_rod = F_gaz - F_inertie).
    """
    theta_rad = math.radians(angle_vilebrequin_deg)
    return force_bielle_n * rayon_manivelle_m * math.sin(theta_rad)
