def calcul_temps_charge(energie_utile_kwh: float, puissance_charge_kw: float, rendement_charge: float) -> float:
    """
    Calcule le temps de charge nécessaire pour restaurer l'énergie utile.

    Formule : t_chg = E_u / (eta_chg * P_chg)

    Args:
        energie_utile_kwh (float): Énergie utile à recharger (E_u) en kWh.
        puissance_charge_kw (float): Puissance de charge disponible (P_chg) en kW.
        rendement_charge (float): Rendement du chargeur (eta_chg), entre 0 et 1.

    Returns:
        float: Temps de charge en heures.
    """
    if rendement_charge <= 0 or rendement_charge > 1:
        raise ValueError("Le rendement doit être entre 0 (exclu) et 1.")
    if puissance_charge_kw <= 0:
        raise ValueError("La puissance de charge doit être positive.")
        
    puissance_effective = puissance_charge_kw * rendement_charge
    return energie_utile_kwh / puissance_effective
