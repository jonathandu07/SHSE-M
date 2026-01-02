def calcul_fem_induite(frequence: float, nombre_spires_serie: int, flux_max_pole: float, facteur_enroulement: float) -> float:
    """
    Calcule la force électromotrice (f.e.m.) induite efficace par phase.

    Formule : E_ph = 4.44 * f * N * Phi_max * k_w

    Args:
        frequence (float): Fréquence électrique (f) en Hz.
        nombre_spires_serie (int): Nombre de spires en série par phase (N).
        flux_max_pole (float): Flux magnétique maximum par pôle (Phi_max) en Webers (Wb).
        facteur_enroulement (float): Facteur d'enroulement (k_w), généralement entre 0.9 et 1.0.

    Returns:
        float: Tension efficace induite par phase (V).
    """
    return 4.44 * frequence * nombre_spires_serie * flux_max_pole * facteur_enroulement

def calcul_fem_induite_avec_induction(frequence: float, nombre_spires_serie: int, induction_gap: float, aire_pole: float, facteur_enroulement: float) -> float:
    """
    Calcule la f.e.m. induite en utilisant l'induction dans l'entrefer.

    Formule : E_ph = 4.44 * f * N * B_g * A_p * k_w
    Cette formule approxime Phi_max = B_g * A_p.

    Args:
        frequence (float): Fréquence (f) en Hz.
        nombre_spires_serie (int): Nombre de spires (N).
        induction_gap (float): Induction magnétique dans l'entrefer (B_g) en Teslas (T).
        aire_pole (float): Aire efficace sous un pôle (A_p) en m².
        facteur_enroulement (float): Facteur d'enroulement (k_w).

    Returns:
        float: Tension efficace induite par phase (V).
    """
    flux_max = induction_gap * aire_pole
    return calcul_fem_induite(frequence, nombre_spires_serie, flux_max, facteur_enroulement)
