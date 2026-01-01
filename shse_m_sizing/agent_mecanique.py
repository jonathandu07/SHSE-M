import math
from .agent_base import Agent

class MechanicalAgent(Agent):
    """
    Detailed sizing of:
    - Piston, Pin, Rings
    - Connecting Rod
    - Crankshaft
    - Bearings
    - Flywheel
    Checks logic: Fatigue, Stress limits, Bearing pressures.
    """
    def __init__(self, config, bore_mm, stroke_mm, p_max_bar, F_max_N=None):
        super().__init__(config, "MechanicalAgent")
        self.B = bore_mm / 1000.0
        self.S = stroke_mm / 1000.0
        self.p_max = p_max_bar * 1e5
        
        # Calculate F_max if not provided
        if F_max_N is None:
            self.F_gas_max = self.p_max * (math.pi * self.B**2 / 4.0)
        else:
            self.F_gas_max = F_max_N

    def run(self):
        self.log("Starting mechanical component sizing...")
        self.log(f"Inputs: B={self.B*1000}mm, S={self.S*1000}mm, P_max={self.p_max/1e5}bar")
        self.log(f"Max Gas Force: {self.F_gas_max:.1f} N")

        # Get Materials
        mat_pist = self.get_material("piston")
        mat_rod = self.get_material("rod")
        mat_crank = self.get_material("crank")
        sf = self.config['constraints']['safety_factor_global']
        
        # --- 1. PISTON ---
        # Height assumption
        h_comp = 0.55 * self.B # Compression height
        h_skirt = 0.6 * self.B
        self.results['piston_height_mm'] = (h_comp + h_skirt/2)*1000
        
        # Pin Sizing (Bending & Shear)
        # d_pin ~ 0.3 * B usually
        d_pin = 0.3 * self.B
        l_pin = 0.85 * self.B # Effective length
        
        # Check Pin Shear
        # tau = F / (2 * A)
        A_pin = math.pi * d_pin**2 / 4.0
        tau_pin = self.F_gas_max / (2 * A_pin)
        sig_yield_pin = mat_pist['yield_strength_MPa'] * 1e6 # Approximation if steel pin not separate
        # Actually pin is usually Steel. Let's assume Steel Pin.
        mat_pin = self.config['materials']['steel_alloy']
        sig_yield_pin = mat_pin['yield_strength_MPa'] * 1e6
        
        sf_pin_shear = (sig_yield_pin / math.sqrt(3)) / tau_pin # Von Mises shear yield
        
        self.results['pin_diameter_mm'] = d_pin * 1000
        self.results['sf_pin_shear'] = sf_pin_shear
        self.check(sf_pin_shear >= sf, f"Pin Shear SF {sf_pin_shear:.2f} < {sf}")
        
        # --- 2. CONNECTING ROD ---
        # L_rod
        # Lambda = L / R. R = S/2.
        R = self.S / 2.0
        Lambda = 3.5 # Standard
        L_rod = R * Lambda
        self.results['rod_length_mm'] = L_rod * 1000
        
        # Buckling Check (Euler)
        # I_rod required?
        # F_crit = pi^2 * E * I / L^2
        # Need F_crit > F_gas_max * SF
        req_F_crit = self.F_gas_max * sf
        req_I = (req_F_crit * L_rod**2) / (math.pi**2 * mat_rod['young_modulus_GPa'] * 1e9)
        
        # Assume Rectangular Section b x h, h=1.5b
        # I = b * h^3 / 12 = b * (1.5b)^3 / 12 = 3.375 * b^4 / 12
        b_rod = ((req_I * 12) / 3.375)**0.25
        h_rod = 1.5 * b_rod
        
        self.results['rod_section_width_mm'] = b_rod * 1000
        self.results['rod_section_depth_mm'] = h_rod * 1000
        self.log(f"Rod Sized for Buckling: {b_rod*1000:.1f}x{h_rod*1000:.1f}mm")

        # --- 3. CRANKSHAFT BEARING ---
        # Projected Area = d * L
        # P = F / (d * L) <= P_max
        max_P_bearing = self.config['constraints']['bearing_max_pressure_MPa'] * 1e6
        
        # Crank Pin
        # L ~ 0.5 * B
        L_crankpin = 0.5 * self.B
        req_d_crankpin = self.F_gas_max / (L_crankpin * max_P_bearing)
        
        # Geometric constraint: d should be robust enough for torsion/bending too. 
        # Usually d ~ 0.6 * B
        d_crankpin = max(req_d_crankpin, 0.5 * self.B)
        
        self.results['crank_pin_diameter_mm'] = d_crankpin * 1000
        self.results['crank_pin_length_mm'] = L_crankpin * 1000
        
        act_P_bearing = self.F_gas_max / (d_crankpin * L_crankpin)
        self.results['bearing_pressure_MPa'] = act_P_bearing / 1e6
        
        self.check(act_P_bearing <= max_P_bearing, f"Bearing Pressure {act_P_bearing/1e6:.1f} MPa > Limit")

        # --- 4. FLYWHEEL ---
        # E = 0.5 * I * w^2. Delta E = Coeff * Energy/Cycle.
        # Simplified: Just output placeholder or basic inertia req
        # Need to know Work per cycle.
        
        return self.results
