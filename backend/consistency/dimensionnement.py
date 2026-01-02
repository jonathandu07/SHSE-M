import math

def calcul_puissance_vilebrequin(
    p_traction_roues_w: float, 
    p_charge_bat_w: float, 
    p_aux_w: float, 
    eta_inverter: float = 0.97, 
    eta_moteur_elec: float = 0.92,
    eta_gen: float = 0.95,
    eta_trans_meca: float = 0.98
) -> float:
    """
    Explicite la chaîne de conversion de puissance.
    Roues -> Moteur Elec -> Onduleur -> Bus DC -> Alternateur -> Vilebrequin.
    """
    # 1. Puissance DC requise par le moteur de traction
    # P_dc_traction = P_roues / (eta_moteur * eta_inverter)
    p_dc_traction = p_traction_roues_w / (eta_moteur_elec * eta_inverter)
    
    # 2. Total Bus DC
    p_dc_total = p_dc_traction + p_charge_bat_w + p_aux_w
    
    # 3. Puissance au Vilebrequin (Sortie Moteur Thermique)
    # P_vilo = P_dc_total / (eta_gen * eta_trans_meca)
    p_vilo = p_dc_total / (eta_gen * eta_trans_meca)
    
    return p_vilo

def calcul_cylindree_totale(
    p_vilo_w: float, 
    pme_pa: float, 
    rpm: float, 
    est_deux_temps: bool = False
) -> float:
    """
    Calcule la cylindrée totale théorique (Vd).
    P = BMEP * Vd * (n/60) / (2 if 4T else 1)
    => Vd = P / (PME * f)
    """
    cycle_factor = 1.0 if est_deux_temps else 2.0
    freq_cycles_hz = (rpm / 60.0) / cycle_factor
    
    if pme_pa <= 0 or freq_cycles_hz <= 0:
        return 0.0
        
    vd_m3 = p_vilo_w / (pme_pa * freq_cycles_hz)
    return vd_m3

def calcul_pme_requise(
    p_vilo_w: float, 
    vd_m3: float, 
    rpm: float, 
    est_deux_temps: bool = False
) -> float:
    """Calcul inverse : PME nécessaire pour une cylindrée donnée."""
    cycle_factor = 1.0 if est_deux_temps else 2.0
    freq_cycles_hz = (rpm / 60.0) / cycle_factor
    
    if vd_m3 <= 0 or freq_cycles_hz <= 0:
        return 0.0
        
    pme_pa = p_vilo_w / (vd_m3 * freq_cycles_hz)
    return pme_pa

def verifier_coherence_physique(
    p_target_w: float, 
    pme_pa: float, 
    vd_m3: float, 
    rpm: float, 
    tolerance: float = 0.01
) -> bool:
    """Vérifie que P = PME * Vd * f à une tolérance près."""
    p_calc = pme_pa * vd_m3 * (rpm / 120.0) # Défaut 4T
    diff = abs(p_calc - p_target_w) / p_target_w
    return diff <= tolerance
