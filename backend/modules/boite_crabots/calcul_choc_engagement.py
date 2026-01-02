def calcul_inertie_equivalente(inertie_primaire: float, inertie_secondaire: float) -> float:
    """
    Calcule l'inertie équivalente pour le choc.

    Formule : J_eq = (J1 * J2) / (J1 + J2)
    """
    if (inertie_primaire + inertie_secondaire) == 0:
        return 0.0
    return (inertie_primaire * inertie_secondaire) / (inertie_primaire + inertie_secondaire)

def calcul_energie_choc(inertie_eq: float, delta_omega_rad_s: float) -> float:
    """
    Calcule l'énergie à dissiper lors du choc d'engagement.

    Formule : Delta E = 0.5 * J_eq * (Delta omega)^2

    Args:
        inertie_eq (float): Inertie équivalente (kg.m²).
        delta_omega_rad_s (float): Différence de vitesse angulaire (rad/s).

    Returns:
        float: Énergie (Joules).
    """
    return 0.5 * inertie_eq * (delta_omega_rad_s**2)

def calcul_couple_synchronisation_moyen(inertie_eq: float, delta_omega_rad_s: float, temps_engagement_s: float) -> float:
    """
    Estime le couple moyen nécessaire pour synchroniser (ou le couple de choc lissé).

    Formule : T_sync = (J_eq * Delta omega) / t_eng
    """
    if temps_engagement_s <= 0:
        raise ValueError("Le temps d'engagement doit être positif.")
    return (inertie_eq * abs(delta_omega_rad_s)) / temps_engagement_s
