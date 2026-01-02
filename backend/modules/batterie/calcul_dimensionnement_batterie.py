def calcul_capacite_totale_batterie(energie_utile_kwh: float, fenetre_soc: float) -> float:
    """
    Calcule la capacité totale de la batterie (E_b) à partir de l'utile (E_u) et de la fenêtre SOC (w).

    Formule : E_b = E_u / w

    Args:
        energie_utile_kwh (float): Énergie utile (kWh).
        fenetre_soc (float): Fenêtre d'utilisation (ex: 0.6 pour 60%), entre 0 et 1.

    Returns:
        float: Capacité totale (kWh).
    """
    if fenetre_soc <= 0 or fenetre_soc > 1:
        raise ValueError("La fenêtre SOC doit être entre 0 (exclu) et 1.")
    return energie_utile_kwh / fenetre_soc

def calcul_poids_batterie(capacite_totale_kwh: float, densite_energetique_kwh_kg: float) -> float:
    """
    Calcule la masse de la batterie.

    Formule : m_b = E_b / rho_E

    Args:
        capacite_totale_kwh (float): Capacité totale (E_b) en kWh.
        densite_energetique_kwh_kg (float): Densité énergétique (rho_E) en kWh/kg.

    Returns:
        float: Masse en kg.
    """
    if densite_energetique_kwh_kg <= 0:
        raise ValueError("La densité énergétique doit être positive.")
    return capacite_totale_kwh / densite_energetique_kwh_kg
