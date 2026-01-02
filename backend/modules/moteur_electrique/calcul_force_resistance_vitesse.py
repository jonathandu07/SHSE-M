import math

def calcul_force_resistance_totale(masse_kg: float, vitesse_ms: float, angle_pente_rad: float, coef_roulement: float, coef_trainee_aero_cda: float, densite_air: float = 1.2, gravite: float = 9.81) -> dict[str, float]:
    """
    Calcule les forces résistantes appliquées au véhicule.

    Args:
        masse_kg (float): Masse totale.
        vitesse_ms (float): Vitesse en m/s.
        angle_pente_rad (float): Angle de la pente en radians (positif en montée).
        coef_roulement (float): Coefficient de résistance au roulement (Crr, ex: 0.015).
        coef_trainee_aero_cda (float): Produit Cd * A (m²).
        densite_air (float): Densité de l'air (kg/m³).
        gravite (float): Accélération pesanteur (m/s²).

    Returns:
        dict: Dictionnaire avec F_roulement, F_aero, F_pente, F_totale.
    """
    force_roulement = masse_kg * gravite * coef_roulement * math.cos(angle_pente_rad)
    force_aero = 0.5 * densite_air * coef_trainee_aero_cda * (vitesse_ms**2)
    force_pente = masse_kg * gravite * math.sin(angle_pente_rad)
    
    total = force_roulement + force_aero + force_pente
    
    return {
        "F_roulement": force_roulement,
        "F_aero": force_aero,
        "F_pente": force_pente,
        "F_totale": total
    }
