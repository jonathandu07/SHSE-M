def calcul_vitesse_moyenne_piston(course_m: float, vitesse_rotation_tr_min: float) -> float:
    """
    Calcule la vitesse moyenne du piston.

    Formule : U_p = 2 * S * (n / 60)

    Args:
        course_m (float): Course du piston (S) en mètres.
        vitesse_rotation_tr_min (float): Régime moteur (n) en tr/min.

    Returns:
        float: Vitesse moyenne en m/s.
    """
    return 2 * course_m * (vitesse_rotation_tr_min / 60.0)
