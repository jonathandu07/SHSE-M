def calcul_pression_gaz_parfait(masse_kg: float, volume_m3: float, temperature_k: float, constante_gaz_r: float = 287.05) -> float:
    """
    Calcule la pression selon la loi des gaz parfaits.
    
    Formule : P = (m * R * T) / V
    """
    if volume_m3 <= 0:
        raise ValueError("Le volume doit être positif.")
        
    return (masse_kg * constante_gaz_r * temperature_k) / volume_m3

def calcul_temperature_compression_adiabatique(t1_k: float, p1_pa: float, p2_pa: float, gamma: float = 1.4) -> float:
    """
    Calcule la température après compression adiabatique.
    
    Formule : T2 = T1 * (P2/P1)^((gamma-1)/gamma)
    """
    return t1_k * ((p2_pa / p1_pa) ** ((gamma - 1) / gamma))
