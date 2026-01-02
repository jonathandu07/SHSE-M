import math

def calcul_force_inertie_alternative(masse_alternative_kg: float, rayon_manivelle_m: float, vitesse_rotation_tr_min: float, longueur_bielle_m: float, angle_vilebrequin_deg: float) -> float:
    """
    Calcule la force d'inertie due aux masses alternatives (piston + axe + partie bielle).

    Formule : F_i = m_eq * r * omega^2 * (cos(theta) + (r/l)*cos(2*theta))

    Args:
        masse_alternative_kg (float): Masse équivalente alternative.
        rayon_manivelle_m (float): Rayon de manivelle (r = Course / 2).
        vitesse_rotation_tr_min (float): Régime moteur.
        longueur_bielle_m (float): Entraxe bielle (l).
        angle_vilebrequin_deg (float): Angle theta (0° au PMH combustion).

    Returns:
        float: Force d'inertie en Newtons (N).
    """
    omega = (2 * math.pi * vitesse_rotation_tr_min) / 60.0
    theta_rad = math.radians(angle_vilebrequin_deg)
    ratio_lambda = rayon_manivelle_m / longueur_bielle_m
    
    terme_trigo = math.cos(theta_rad) + (ratio_lambda * math.cos(2 * theta_rad))
    
    return masse_alternative_kg * rayon_manivelle_m * (omega**2) * terme_trigo
