def calcul_pertes_fer_steinmetz(k_h: float, frequence: float, induction_max: float, exposant_steinmetz: float, k_e: float) -> float:
    """
    Estime les pertes fer volumiques ou massiques selon les coefficients fournis (Steinmetz + Foucault).
    
    Formule : P_fe = k_h * f * B^x + k_e * f^2 * B^2

    Args:
        k_h (float): Coefficient d'hystérésis.
        frequence (float): Fréquence (f) en Hz.
        induction_max (float): Induction maximale (B) en Teslas.
        exposant_steinmetz (float): Exposant 'x' (souvent entre 1.5 et 2.5).
        k_e (float): Coefficient de pertes par courants de Foucault (Eddy currents).

    Returns:
        float: Pertes fer (W/kg ou W/m3 selon l'unité des coefficients k).
    """
    pertes_hyst = k_h * frequence * (induction_max ** exposant_steinmetz)
    pertes_eddy = k_e * (frequence ** 2) * (induction_max ** 2)
    return pertes_hyst + pertes_eddy
