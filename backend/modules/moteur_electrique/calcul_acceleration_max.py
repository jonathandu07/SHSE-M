def calcul_acceleration_max(mu_adherence: float, charge_essieu_moteur_n: float, force_resistance_n: float, masse_kg: float, hauteur_cg_m: float, empattement_m: float, type_milieu: str = 'fwd') -> float:
    """
    Calcule l'accélération maximale limitée par l'adhérence (avec transfert de masse simplifié).
    
    Attention: Cette fonction utilise une approximation directe. Pour plus de précision, il faut résoudre le système couplé (accélération <-> transfert de charge).
    Ici on suppose que 'charge_essieu_moteur_n' est la charge statique ou quasi-statique déjà calculée, ou alors on utilise la formule analytique complète si on avait tous les paramètres.
    
    Pour simplifier selon le doc, on fournit ici la formule analytique directe si possible.
    
    a_max_fwd = (mu * (g*cos*lr - g*sin*h) - Fres/m) / (1 + mu*h/L)
    """
    # Note: Cette implémentation requiert d'être appelée avec les bons paramètres contextuels.
    # Pour faire simple et modulaire, on va implémenter la relation F_max = mu * N
    
    force_max_adherence = mu_adherence * charge_essieu_moteur_n
    accel_max = (force_max_adherence - force_resistance_n) / masse_kg
    return accel_max

def calcul_acceleration_max_analytique(mu: float, masse: float, g: float, lr: float, lf: float, h: float, L: float, theta: float, Fres: float, mode: str = 'FWD') -> float:
    """
    Formule analytique complète pour a_max (tenant compte du transfert de charge dynamique).
    """
    import math
    cos_theta = math.cos(theta)
    sin_theta = math.sin(theta)
    
    if mode == 'FWD':
        numerateur = mu * ((g * cos_theta * lr / L) - (g * sin_theta * h / L)) - (Fres / masse)
        denominateur = 1 + (mu * h / L)
    elif mode == 'RWD':
        numerateur = mu * ((g * cos_theta * lf / L) + (g * sin_theta * h / L)) - (Fres / masse)
        denominateur = 1 - (mu * h / L)
    else:
        raise ValueError("Mode doit être 'FWD' ou 'RWD'.")
        
    return numerateur / denominateur
