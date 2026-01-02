import math

def calcul_force_tangentielle(couple_nm: float, diametre_primitif_m: float) -> float:
    """
    Calcule l'effort tangentiel sur un pignon.

    Formule : F_t = 2 * T / d

    Args:
        couple_nm (float): Couple transmis (T) en N.m.
        diametre_primitif_m (float): Diamètre primitif (d) en mètres.

    Returns:
        float: Force tangentielle (F_t) en Newtons (N).
    """
    if diametre_primitif_m <= 0:
        raise ValueError("Le diamètre primitif doit être positif.")
    return (2 * couple_nm) / diametre_primitif_m

def calcul_forces_engrenage(force_tangentielle: float, angle_pression_deg: float = 20.0, angle_helice_deg: float = 0.0) -> dict[str, float]:
    """
    Calcule les composantes radiale et axiale des efforts d'engrenage.

    Formules :
        F_r = F_t * tan(phi) / cos(beta)
        F_a = F_t * tan(beta)

    Args:
        force_tangentielle (float): Force tangentielle (F_t) en N.
        angle_pression_deg (float): Angle de pression (phi) en degrés (standard 20°).
        angle_helice_deg (float): Angle d'hélice (beta) en degrés (0° pour denture droite).

    Returns:
        dict: {'F_r': float, 'F_a': float} en Newtons.
    """
    phi_rad = math.radians(angle_pression_deg)
    beta_rad = math.radians(angle_helice_deg)
    
    force_radiale = (force_tangentielle * math.tan(phi_rad)) / math.cos(beta_rad)
    force_axiale = force_tangentielle * math.tan(beta_rad)
    
    return {"F_r": force_radiale, "F_a": force_axiale}
