import math
from .config import InputParameters, DimensionResults

def dimension_components(inputs: InputParameters, res: DimensionResults) -> DimensionResults:
    """
    Calculates detailed dimensions for all sub-components.
    """
    
    # 1. Bore & Stroke
    R_sb = inputs.limits.S_over_B
    res.Bore = (4.0 * res.Vd_cyl / (math.pi * R_sb))**(1.0/3.0)
    res.Stroke = res.Bore * R_sb
    
    # 2. Kinematics
    res.U_mean = 2.0 * res.Stroke * inputs.N_rpm / 60.0
    res.crank_radius = res.Stroke / 2.0
    res.rod_length = res.crank_radius * inputs.limits.rod_lambda
    omega = 2 * math.pi * inputs.N_rpm / 60.0
    
    # 3. Forces
    res.p_max = inputs.p_me_target_pa / inputs.limits.phi
    res.F_max = res.p_max * (math.pi * res.Bore**2 / 4.0)
    res.Torque_mean = res.P_shaft_req / omega
    
    # Material Allowables
    sigma_adm_steel = inputs.limits.sigma_adm_steel / inputs.limits.safety_factor
    sigma_adm_alum = inputs.limits.sigma_adm_alum / inputs.limits.safety_factor
    tau_adm_steel = sigma_adm_steel * 0.58 # Shear assumption

    ## --- DETAILED COMPONENTS ---

    # A. PISTON GROUP
    res.piston_diameter = res.Bore
    # Pin Diameter (Empirical: ~0.25-0.35 * B) based on bending/shear
    # d_pin calculated from bending moment M = F_max * L/4 ? No, usually F_max * D/8 roughly.
    # Let's use empirical check: d_pin ~ 0.3 * Bore
    res.pin_diameter = 0.3 * res.Bore
    res.pin_length = 0.85 * res.Bore # Somewhat shorter than bore
    
    # Piston Heights (Empirical)
    res.piston_compression_height = 0.5 * res.Bore # Pin center to top
    res.piston_skirt_height = 0.6 * res.Bore
    res.piston_height = res.piston_compression_height + res.piston_skirt_height * 0.5 # Total height approx
    
    # Rings (SAE Standard approx)
    # Compression rings: b = B / 25 approx
    res.ring_height = res.Bore / 25.0
    res.ring_width = res.Bore / 22.0
    res.num_rings = 3
    
    # Piston Crown Thickness (Plate bending)
    # t = D * sqrt(3 * p_max / (16 * sigma))
    res.piston_top_thickness = res.Bore * math.sqrt(3.0 * res.p_max / (16.0 * sigma_adm_alum))

    # B. CONNECTING ROD
    # Small end (Pied): OD ~ Pin + 2*wall. Wall ~ 0.2*Pin
    res.rod_small_end_diameter = res.pin_diameter * 1.5 
    
    # Big end (Tête): Pin diameter (Crankpin)
    # Crankpin Diameter check vs Bearing Pressure & Bending
    # P_bearing_max ~ 10-15 MPa for industrial engines.
    # F_max = P_bearing * d_pin * L_pin
    # Assume L_pin ~ 0.5 * Bore
    res.crank_pin_length = 0.45 * res.Bore
    res.crank_pin_diameter = res.F_max / (15e6 * res.crank_pin_length) # Limit bearing pressure 15 MPa
    res.crank_pin_diameter = max(res.crank_pin_diameter, 0.4 * res.Bore) # Min geometry constraint
    
    res.rod_big_end_diameter = res.crank_pin_diameter * 1.4 # Rough estimate housing
    res.rod_big_end_width = res.crank_pin_length * 0.95
    
    # Rod Beam Section (I-beam)
    # Area ~ F_max / sigma_comp
    # For buckling, verify Ixx.
    # Simplified: Width ~ 0.6 * BigEndWidth, Depth ~ 1.5 * Width
    # We set dimensions, Check.py will verify buckling.
    res.rod_column_section_width = res.rod_big_end_width * 0.4
    res.rod_column_section_depth = res.rod_column_section_width * 1.8
    
    # Rod Bolts (2 bolts)
    # F_inertia_tensile ~ m_piston * omega^2 * r * (1 + 1/lambda) at TDC exhaust
    # Conservative F_bolt_load ~ F_max (tensile is usually less than compression, but verify)
    # Let's size for F_max/2 per bolt to be safe (simplified)
    # A_bolt * sigma = F_max / 2
    a_bolt = (res.F_max / 2.0) / sigma_adm_steel
    res.rod_bolt_diameter = math.sqrt(4.0 * a_bolt / math.pi)

    # C. CRANKSHAFT
    # Main Journals (Tourillons)
    # Usually larger than pins.
    res.main_journal_diameter = res.crank_pin_diameter * 1.2
    res.main_journal_length = res.crank_pin_length * 0.8
    
    # Webs (Bras)
    # t * w * sigma ~ bending.
    res.web_thickness = 0.25 * res.Bore
    res.web_width = 1.3 * res.main_journal_diameter
    
    # Overlap
    # (Main_D + Pin_D)/2 - Stroke/2
    res.overlap = (res.main_journal_diameter + res.crank_pin_diameter)/2.0 - res.crank_radius
    
    # D. CYLINDER / BLOCK
    # Wall thickness (Lamé / Thin Cylinder)
    res.wall_thickness = (res.p_max * res.Bore) / (2.0 * sigma_adm_alum) + 0.002 # +2mm casting margin
    res.cyl_outer_diameter = res.Bore + 2.0 * res.wall_thickness + 0.015 # +Water jacket space
    
    # Head Bolts (Goujons)
    # F_gas = p_max * Area. 4 bolts.
    # F_bolt = F_gas / 4.
    f_bolt = res.F_max / 4.0
    a_head_bolt = f_bolt / sigma_adm_steel
    res.head_bolt_diameter = math.sqrt(4.0 * a_head_bolt / math.pi)
    res.num_head_bolts = 4

    # E. FLYWHEEL (Detailed)
    work_cycle = res.P_indicated_req / (inputs.N_rpm / 60.0)
    delta_E = work_cycle * 0.15 # 15% fluct
    if inputs.N_cyl > 1:
        delta_E /= inputs.N_cyl
        
    res.flywheel_inertia = delta_E / (omega**2 * inputs.limits.flywheel_Cf)
    # Rim Type Flywheel: I = m * r^2.
    # Let r_mean = 1.6 * Stroke
    r_fly_mean = 1.6 * res.Stroke
    res.flywheel_diameter = 2.0 * (r_fly_mean + 0.02) # Outer
    res.flywheel_mass = res.flywheel_inertia / (r_fly_mean**2)
    # Width estimate (Steel density 7800)
    # Volume = Mass / 7800
    # Volume ~ 2*pi*r_mean * h * t. Assume t (rim thickness) = 4cm
    t_rim = 0.04
    vol_fly = res.flywheel_mass / 7800.0
    res.flywheel_width = vol_fly / (2.0 * math.pi * r_fly_mean * t_rim) 
    
    # Water Jacket
    res.water_jacket_area = math.pi * (res.Bore + 2*res.wall_thickness) * res.Stroke

    return res
