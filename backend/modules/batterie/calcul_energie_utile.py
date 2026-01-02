def calcul_energie_utile_cible(temps_charge_cible_h: float, puissance_charge_kw: float, rendement_charge: float) -> float:
    """
    Calcule l'énergie utile dimensionnée par une cible de temps de recharge (Ratio Recharge/Capacité).
    
    Formule : E_u = eta_chg * P_chg * t_chg
    """
    return rendement_charge * puissance_charge_kw * temps_charge_cible_h

def calcul_energie_utile_trajet(distance_km: float, conso_kwh_km: float) -> float:
    """
    Calcule l'énergie utile pour une autonomie EV donnée.
    
    Formule : E = d * conso
    """
    return distance_km * conso_kwh_km

def calcul_energie_utile_pic(puissance_pic_kw: float, duree_secondes: float) -> float:
    """
    Calcule l'énergie utile tampon pour absorber un pic de puissance.
    
    Formule : E = (P * t) / 3600  (pour avoir des kWh)
    """
    return (puissance_pic_kw * duree_secondes) / 3600.0

def choisir_energie_utile_finale(*args) -> float:
    """
    Retourne la valeur maximale parmi plusieurs critères d'énergie utile.
    """
    return max(args)
