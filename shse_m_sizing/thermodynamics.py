import math
from .config import InputParameters, DimensionResults

def calculate_thermodynamics(inputs: InputParameters) -> DimensionResults:
    """
    Calculates power requirements and displacement based on targets.
    """
    res = DimensionResults()
    
    # 1. Power Chain
    # P_batt = P_shaft * eta_gen * eta_elec * eta_charge
    eta_chain_shaft_to_batt = inputs.eta.eta_gen * inputs.eta.eta_elec * inputs.eta.eta_charge
    res.P_shaft_req = inputs.P_batt_target * 1000.0 / eta_chain_shaft_to_batt  # Watts
    
    # P_indicated = P_shaft / eta_m
    res.P_indicated_req = res.P_shaft_req / inputs.eta.eta_m
    
    # 2. Displacement
    # P_i = p_me * Vd_total * (N/60)
    # Vd_total = P_i * 60 / (p_me * N)
    if inputs.N_rpm <= 0:
        raise ValueError("RPM must be positive")
    if inputs.p_me_target_pa <= 0:
        raise ValueError("MEP must be positive")
        
    res.Vd_total = (res.P_indicated_req * 60.0) / (inputs.p_me_target_pa * inputs.N_rpm) # m^3
    res.Vd_cyl = res.Vd_total / inputs.N_cyl
    
    return res
