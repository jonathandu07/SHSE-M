import math

def calcul_charges_essieux(masse_kg: float, acceleration_ms2: float, angle_pente_rad: float, empattement_l_m: float, dist_cg_arriere_lr_m: float, dist_cg_avant_lf_m: float, hauteur_cg_h_m: float, gravite: float = 9.81) -> dict[str, float]:
    """
    Calcule les charges normales sur les essieux avant et arrière en tenant compte du transfert de charge.
    
    Args:
        masse_kg (float): Masse véhicule.
        acceleration_ms2 (float): Accélération longitudinale (positive = accélération).
        angle_pente_rad (float): Pente.
        empattement_l_m (float): Empattement total (L).
        dist_cg_arriere_lr_m (float): Distance CG -> Essieu Arrière.
        dist_cg_avant_lf_m (float): Distance CG -> Essieu Avant.
        hauteur_cg_h_m (float): Hauteur CG.
    
    Returns:
        dict: {'N_avant': float, 'N_arriere': float} en Newtons.
    """
    terme_commun_g = masse_kg * gravite
    terme_inertie = masse_kg * acceleration_ms2 * hauteur_cg_h_m
    terme_pente_h = terme_commun_g * math.sin(angle_pente_rad) * hauteur_cg_h_m
    
    # N_f = (mg cos(theta) * lr - m*a*h - mg sin(theta) * h) / L
    n_avant = (terme_commun_g * math.cos(angle_pente_rad) * dist_cg_arriere_lr_m - terme_inertie - terme_pente_h) / empattement_l_m
    
    # N_r = (mg cos(theta) * lf + m*a*h + mg sin(theta) * h) / L
    n_arriere = (terme_commun_g * math.cos(angle_pente_rad) * dist_cg_avant_lf_m + terme_inertie + terme_pente_h) / empattement_l_m
    
    return {"N_avant": n_avant, "N_arriere": n_arriere}
