import math
from .config import InputParameters, DimensionResults

def dimension_components(inputs: InputParameters, res: DimensionResults) -> DimensionResults:
    """
    Calculates dimensions S, B, and component sizes based on Vd and power.
    """
    
    # 1. Bore & Stroke
    # Vd = (pi/4) * B^2 * S
    # S = R_sb * B
    # Vd = (pi/4) * B^3 * R_sb => B = (4 * Vd / (pi * R_sb))^(1/3)
    R_sb = inputs.limits.S_over_B
    res.Bore = (4.0 * res.Vd_cyl / (math.pi * R_sb))**(1.0/3.0)
    res.Stroke = res.Bore * R_sb
    
    # 2. Kinematics
    res.U_mean = 2.0 * res.Stroke * inputs.N_rpm / 60.0
    res.crank_radius = res.Stroke / 2.0
    res.rod_length = res.crank_radius * inputs.limits.rod_lambda
    omega = 2 * math.pi * inputs.N_rpm / 60.0
    
    # 3. Forces & Pressures
    # p_me = phi * p_max => p_max = p_me / phi
    res.p_max = inputs.p_me_target_pa / inputs.limits.phi
    res.F_max = res.p_max * (math.pi * res.Bore**2 / 4.0)
    res.Torque_mean = res.P_shaft_req / omega
    
    # 4. Component Sizing
    
    # Cylinder Wall (Thin-walled assumption + Safety Factor)
    # t = P * D / (2 * sigma)
    # We use Bore as D approximately, strictly D_internal
    allowable_stress_alum = inputs.limits.sigma_adm_alum / inputs.limits.safety_factor
    res.wall_thickness = (res.p_max * res.Bore) / (2.0 * allowable_stress_alum)
    # Min thickness constraint (manufacturing)
    res.wall_thickness = max(res.wall_thickness, 0.003) 
    res.cyl_outer_diameter = res.Bore + 2.0 * res.wall_thickness
    
    # Water Jacket (Rough estimation based on power to reject)
    # Q_reject ~ P_fuel * (1-eta_th) * fraction_to_coolant (~0.3 of reject)
    # This is a dimensional placeholder for the Area
    # Surface area of cylinder ~ pi * B * S
    res.water_jacket_area = math.pi * (res.cyl_outer_diameter + 0.005) * res.Stroke
    
    # Connecting Rod (Simplified Column Buckling - Euler)
    # F_crit = pi^2 * E * I / L^2. We need F_crit > F_max * SF
    # Steel E ~ 210 GPa. 
    # Assume Circular section diameter d_rod. I = pi * d^4 / 64
    # F_max * SF = pi^2 * E * (pi * d^4 / 64) / L^2
    # d^4 = (F_max * SF * L^2 * 64) / (pi^3 * E)
    E_steel = 210e9
    d4 = (res.F_max * inputs.limits.safety_factor * res.rod_length**2 * 64.0) / (math.pi**3 * E_steel)
    res.rod_diameter = d4**0.25
    
    # Crankpin (Shear/Bending simplified)
    # Double shear or bending is dominant. Approximated by bearing pressure limit or bending stress.
    # Let's use bending stress on the pin as a cantilever (conservative) or simple beam.
    # sigma = M * y / I. M ~ F_max * L_pin/2. Let L_pin ~ 0.5 * B.
    # This is complex without detailed design. We will scale based on shaft torque and F_max.
    # Simplified: d_pin ~ 0.4 * B is a common starting point in engines, checked vs stress.
    # Let's calculate d_pin based on bending stress limit.
    # M = F_max * (res.Bore * 0.2) # assumption arm
    # sigma_adm = 400MPa/SF
    # S_modulus = pi * d^3 / 32
    # M / S_modulus <= sigma_adm
    sigma_adm_steel = inputs.limits.sigma_adm_steel / inputs.limits.safety_factor
    moment_arm = res.Bore * 0.25 # Assumption for pin width contrib
    bending_moment = res.F_max * moment_arm
    # d^3 = 32 * M / (pi * sigma_adm)
    res.pin_diameter = ((32.0 * bending_moment) / (math.pi * sigma_adm_steel))**(1.0/3.0)
    
    # Flywheel
    # E_kinetic = 0.5 * J * omega^2
    # Delta_E = P_shaft * 60/N (Energy per rev) * Cf (simplified)
    # Actually Delta_E = Work_per_cycle * Cf. 
    # J = Delta_E / (omega^2 * Cf_speed) -> Using slightly different formulation
    # J * omega * delta_omega = Delta_E => J = Delta_E / (omega^2 * coeff_fluctuation_speed)
    # Let's use Work per cycle = P_indicated * 2 / (N/60) (since 1 power stroke per rev? Prompt says "2 chambres... piston moteur... fourni travail", implies 2-stroke like or double acting?)
    # Prompt: "Chambre chaude... Piston séparateur... Chambre froide... Piston moteur". 
    # Valid assumption for sizing: 1 active expansion stroke per revolution per cylinder or similar.
    # Work_cycle = P_i / (N/60).
    work_cycle = res.P_indicated_req / (inputs.N_rpm / 60.0)
    delta_E = work_cycle * 0.1 # Assumption: Energy fluctuation ~ 10-20% of work cycle if single cyl
    if inputs.N_cyl > 1:
        delta_E /= inputs.N_cyl # Smoother with more cyl
        
    # J = Delta_E / (omega^2 * Cf)
    res.flywheel_inertia = delta_E / (omega**2 * inputs.limits.flywheel_Cf)
    
    # Solid disk assumption for Mass: J = 1/2 * m * r^2
    # Assume r = 1.5 * Stroke (reasonable size)
    r_fly = 1.5 * res.Stroke
    res.flywheel_diameter = 2.0 * r_fly
    res.flywheel_mass = 2.0 * res.flywheel_inertia / (r_fly**2)
    
    return res
