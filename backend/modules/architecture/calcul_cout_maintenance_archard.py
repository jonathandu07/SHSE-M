def calcul_cout_maintenance_estime(duree_usage_h: float, duree_vie_joint_base_h: float, charge_nominale_n: float, charge_actuelle_n: float, nb_joints_base: int, nb_joints_actuel: int, cout_inter_eur: float) -> float:
    """
    Estime le coût de maintenance relatif à l'usure des joints selon le nombre de cylindres.
    
    Formule : Cost = N_inter * (N_seal * C_seal + C_stop)
                 avec N_inter ~ T / L_seal
                 et L_seal = L0 * (W0 / W)^beta
    
    Cette fonction simplifiée retourne un score de coût monétaire.
    
    Args:
        duree_usage_h (float): Horizon d'utilisation (T).
        duree_vie_joint_base_h (float): Durée vie référence (L0).
        charge_nominale_n (float): Charge référence (W0).
        charge_actuelle_n (float): Charge réelle (W) = W0 * (N_base/N_actuel).
        nb_joints_base (int): Nombre joints réf.
        nb_joints_actuel (int): Nombre joints config actuelle.
        cout_inter_eur (float): Coût forfaitaire d'une intervention (pièces + MO + arrêt).
        
    Returns:
        float: Coût total estimé (EUR).
    """
    beta_wear = 1.5 # Exposant empirique d'usure
    
    if charge_actuelle_n <= 0: return 0.0
    
    # Durée de vie améliorée par la baisse de charge
    duree_vie_estimee = duree_vie_joint_base_h * ((charge_nominale_n / charge_actuelle_n) ** beta_wear)
    
    # Nombre d'interventions sur la période
    nb_interventions = duree_usage_h / duree_vie_estimee
    
    # Coût intervention facteur nb joints
    cout_par_inter = cout_inter_eur * (nb_joints_actuel / nb_joints_base)
    
    cost_total = nb_interventions * cout_par_inter
    return cost_total
