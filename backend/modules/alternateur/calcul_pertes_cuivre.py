def calcul_resistance_enroulement(resistivite: float, longueur_fil: float, section_fil: float) -> float:
    """
    Calcule la résistance d'un enroulement.

    Formule : R = rho * L / A

    Args:
        resistivite (float): Résistivité du matériau (rho) en Ohm.m (ex: Cuivre a 20°C approx 1.7e-8).
        longueur_fil (float): Longueur totale du fil (L) en mètres.
        section_fil (float): Section du fil (A) en m².

    Returns:
        float: Résistance en Ohms.
    """
    if section_fil <= 0:
         raise ValueError("La section du fil doit être positive.")
    return resistivite * longueur_fil / section_fil

def calcul_pertes_cuivre_triphase(courant_phase: float, resistance_phase: float) -> float:
    """
    Calcule les pertes cuivre totales pour un système triphasé.

    Formule : P_cu = 3 * I_ph^2 * R_ph

    Args:
        courant_phase (float): Courant efficace par phase (I_ph) en Ampères.
        resistance_phase (float): Résistance d'une phase (R_ph) en Ohms.

    Returns:
        float: Pertes puissance totales en Watts (W).
    """
    return 3 * (courant_phase**2) * resistance_phase

def calcul_pertes_cuivre_phase(courant: float, resistance: float) -> float:
    """
    Calcule les pertes cuivre pour un seul enroulement.
    Formule: P = I^2 * R
    """
    return (courant**2) * resistance
