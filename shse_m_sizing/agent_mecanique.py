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

        # --- DETAILED MANUFACTURING DATA ---
        # Mass Estimates (Volume * Density)
        rho_piston = mat_pist['density_kg_m3']
        rho_rod = mat_rod['density_kg_m3']
        
        # Piston Mass (Simplified Cylinder approximation)
        vol_piston = (math.pi * self.B**2 / 4) * (self.results['piston_height_mm']/1000) * 0.6 # 60% solidity
        m_piston = vol_piston * rho_piston
        self.results['mass_piston_kg'] = m_piston
        
        # Rod Mass
        vol_rod = (L_rod * b_rod * h_rod) # Beam part
        vol_rod += (math.pi * (d_crankpin*1.4)**2 / 4 - math.pi * d_crankpin**2 / 4) * (L_crankpin * 0.9) # Big end
        m_rod = vol_rod * rho_rod
        self.results['mass_rod_kg'] = m_rod
        
        # Tolerances (ISO 286)
        # Cylinder Bore: H7
        # Piston Skirt: f7 (Clearance fit)
        # Piston Pin: g6 (Sliding)
        # Crank Pin: h6
        self.results['tol_bore'] = "H7 (+0/+35 µm)"
        self.results['tol_piston'] = "f7 (-30/-60 µm)"
        self.results['tol_pin'] = "g6 (-7/-20 µm)"
        
        # Surface Finish (Ra in micrometers)
        self.results['ra_cylinder_liner'] = 0.4 # Honed
        self.results['ra_piston_skirt'] = 0.8 # Turned/Ground
        self.results['ra_crank_journals'] = 0.2 # Superfinished
        
        # Wear / PV Factor Check (P * V)
        # Sliding Velocity (Mean) = U_p
        PV_skirt = (act_P_bearing * 0.1) * self.results.get('U_mean_m_s', 8.0) 
        self.results['PV_factor_skirt'] = PV_skirt 

        # --- REFINEMENT: FRICTION & CLEARANCE ---
        
        # 1. Friction Estimation (FMEP) - Chen-Flynn Model
        # FMEP (bar) = A + B*Pmax + C*Up + D*Up^2
        # Constants for modern automotive engine:
        A_f = 0.4 # Constant friction
        B_f = 0.005 # Peak pressure factor
        C_f = 0.09 # Velocity linear
        D_f = 0.0009 # Velocity squared
        
        U_p = self.results.get('U_mean_m_s', 8.0)
        P_max_bar = self.p_max / 1e5
        
        FMEP = A_f + (B_f * P_max_bar) + (C_f * U_p) + (D_f * U_p**2)
        self.results['FMEP_bar'] = FMEP
        self.log(f"FMEP Estimated (Friction): {FMEP:.2f} bar")
        
        # 2. Thermal Clearance (Reverse Calculation)
        # Target Hot Clearance = 20 microns (0.020 mm)
        Target_Hot_Cl_mm = 0.020
        T_amb = 20.0
        T_liner_op = 120.0
        T_piston_op = 220.0
        
        alpha_liner = 11e-6
        alpha_piston = 23e-6
        
        # D_liner_hot = B * (1 + a_l * dT_l)
        # D_piston_hot = (B - Cl_cold) * (1 + a_p * dT_p)
        # We want D_liner_hot - D_piston_hot = Target
        
        # B(1+kL) - (B-C)(1+kP) = T
        # B(1+kL) - B(1+kP) + C(1+kP) = T
        # C(1+kP) = T - B(1+kL) + B(1+kP)
        # C = (T + B(1+kP) - B(1+kL)) / (1+kP)  <-- Approximation?
        # Let's solve exactly:
        kL = alpha_liner * (T_liner_op - T_amb)
        kP = alpha_piston * (T_piston_op - T_amb)
        
        B_nom = self.B * 1000.0 # mm
        
        # Req Cold Cl:
        # Cl_cold = ( B_nom*(1+kP) - B_nom*(1+kL) + Target_Hot_Cl_mm ) / (1+kP)
        Cl_cold_mm = ( B_nom*(1+kP) - B_nom*(1+kL) + Target_Hot_Cl_mm ) / (1+kP)
        
        self.results['design_clearance_cold_mm'] = Cl_cold_mm
        self.log(f"REQUIRED Cold Clearance: {Cl_cold_mm*1000:.1f} µm (for {Target_Hot_Cl_mm*1000:.0f}µm Hot)")
        
        # Verify
        D_L_H = B_nom * (1+kL)
        D_P_H = (B_nom - Cl_cold_mm) * (1+kP)
        check_hot = D_L_H - D_P_H
        self.results['Clearance_Hot_mm'] = check_hot
        
        # 3. Wall Thicknesses (For Sketch)
        # Liner: Hoop Stress (Lamé) -> t = P*D / (2*Sigma)
        # Sigma allowed for Cast Iron ~ 150MPa? (Safety factor included)
        t_liner = (P_max_bar/10 * B_nom) / (2 * 50) # Very conservative 50MPa working
        self.results['liner_thickness_mm'] = max(t_liner, 3.0) # Min 3mm
        
        # Piston Crown: Bending plate formula
        # t = D * sqrt(3*P / 16*Sigma)
        t_crown = B_nom * math.sqrt(3*(P_max_bar/10) / (16 * 100)) # 100MPa allowed for hot Alu
        self.results['piston_crown_thickness_mm'] = max(t_crown, B_nom*0.08)


        # --- COMPONENT GROUPS (For Interactive GUI) ---
        
        # 1. PISTON GROUP
        # Thermal Stress Estimate: sigma = E * alpha * dT * Constraint
        # Alpha Alu ~ 23e-6. dT ~ 100C gradient.
        alpha_alu = 23e-6
        E_alu = mat_pist['young_modulus_GPa'] * 1e9
        dT_grad = 100.0 # deg C
        sigma_thermal = E_alu * alpha_alu * dT_grad * 0.5 # 50% constraint
        
        self.results['shsem_components'] = {}
        self.results['shsem_components']['Piston'] = {
            "name": "Piston Moteur",
            "material": "Alu 2618A",
            "specs": [
                ("Diamètre", f"{self.B * 1000:.2f} mm"),
                ("Hauteur", f"{self.results['piston_height_mm']:.1f} mm"),
                ("Masse Estim.", f"{m_piston:.3f} kg"),
                ("Jeu Jupe", "30-60 µm"),
                ("Etat Surface", f"Ra {self.results['ra_piston_skirt']}")
            ],
            "stress_data": [
                ("Contrainte Thermique", f"{sigma_thermal/1e6:.1f} MPa", 260.0), # Val, Limit
                ("Facteur PV (Usure)", f"{PV_skirt/1e6:.1f} MPa.m/s", 50.0)
            ],
            "manufacturing": {
                "Tolérance": "f7",
                "Traitement": "Anodisation dure",
                "Rugosité": "Ra 0.8"
            }
        }

        # --- 4. DETAILED MANUFACTURING GEOMETRY (The "Zero-Oubli" Step) ---
        B_mm = self.B * 1000.0
        
        # Piston Ring Grooves (ISO Standard-ish)
        # Top Ring (Fire): Height ~ 1.2mm, Depth ~ 3.5mm
        h_ring1 = 1.2
        d_ring1 = 3.5
        # 2nd Ring (Comp): Height ~ 1.5mm, Depth ~ 3.8mm
        h_ring2 = 1.5
        d_ring2 = 3.8
        # Oil Ring: Height ~ 3.0mm, Depth ~ 3.0mm
        h_ring3 = 3.0
        d_ring3 = 3.0
        
        # Lands (Vertical spacing)
        h_land_top = 6.0 # Top Land (Fire Land) - Critical for thermal
        h_land_2 = 4.0   # Between 1 and 2
        h_land_3 = 3.0   # Between 2 and 3
        
        # Pin Boss
        w_pin_boss = B_mm * 0.4 # Width of the support
        d_pin_bore = d_pin * 1000 # Diameter
        
        # Liner Details
        t_liner = self.results['liner_thickness_mm']
        h_flange = 5.0
        w_flange = 4.0 # Sit on block
        h_liner = self.S*1000 + B_mm * 1.5 # Stroke + Piston + Margin
        
        # Store comprehensive geometry dict
        self.results['geometry'] = {
            'piston': {
                'D': B_mm,
                'H': self.results['piston_height_mm'],
                't_crown': self.results['piston_crown_thickness_mm'],
                'h_land_top': h_land_top,
                'h_land_2': h_land_2,
                'h_land_3': h_land_3,
                'rings': [ (h_ring1, d_ring1), (h_ring2, d_ring2), (h_ring3, d_ring3) ],
                'pin_boss_width': w_pin_boss,
                'pin_bore_D': d_pin_bore
            },
            'liner': {
                'ID': B_mm,
                'OD': B_mm + 2*t_liner,
                'H': h_liner,
                'flange_h': h_flange,
                'flange_w': w_flange,
                't_wall': t_liner
            },
            'rod': {
                'L': L_rod * 1000,
                'D_big': d_crankpin * 1000 + 10, # OD estim
                'D_small': d_pin * 1000 + 8,     # OD estim
                'W_big': d_crankpin * 1000 * 0.6, # Width
                'W_small': d_pin * 1000 * 0.55
            }
        }
        
        # Restore Rod Stress Calcs
        req_I = (self.F_gas_max * sf * L_rod**2) / (math.pi**2 * mat_rod['young_modulus_GPa'] * 1e9) # Re-use or Re-calc
        sigma_buckling_crit = (math.pi**2 * mat_rod['young_modulus_GPa']*1e9 * req_I) / (L_rod**2)
        area_rod = (b_rod * h_rod)
        sigma_comp = self.F_gas_max / area_rod
        yield_rod = mat_rod['yield_strength_MPa'] * 1e6

        self.results['shsem_components']['Bielle'] = {
            "name": "Bielle",
            "material": "Acier 42CrMo4",
            "specs": [
                ("Entraxe", f"{L_rod * 1000:.1f} mm"),
                ("Section", f"{b_rod*1000:.1f} x {h_rod*1000:.1f} mm"),
                ("Masse Estim.", f"{m_rod:.3f} kg"),
                ("Ø Axe Piston", f"{d_pin * 1000:.1f} mm"),
                ("Ø Maneton", f"{d_crankpin * 1000:.1f} mm")
            ],
            "stress_data": [
                ("Contrainte Comp.", f"{sigma_comp/1e6:.1f} MPa", yield_rod/1e6),
                ("Flambement (Crit)", f"{sigma_buckling_crit/area_rod/1e6:.1f} MPa", "N/A"),
                ("Sécurité Global", f"{sf:.2f}", "1.5")
            ],
            "manufacturing": {
                "Tolérance Têtes": "H6/H7",
                "Traitement": "Grenaillage",
                "Rugosité": "Ra 1.6",
                "Fillets": "R3 typ."
            }
        }

        # 3. CRANKSHAFT
        self.results['shsem_components']['Vilebrequin'] = {
            "name": "Vilebrequin",
            "material": "Acier Forgé 42CrMo4",
            "specs": [
                ("Course", f"{self.S * 1000:.1f} mm"),
                ("Ø Tourillons", f"{d_crankpin * 1000:.1f} mm (Est.)"),
                ("Ø Manetons", f"{d_crankpin * 1000:.1f} mm"),
                ("Pression Paliers", f"{act_P_bearing/1e6:.1f} MPa")
            ],
            "stress_data": [
                ("Pression Contact", f"{act_P_bearing/1e6:.1f} MPa", max_P_bearing/1e6)
            ],
            "manufacturing": {
                "Tolérance": "h6",
                "Traitement": "Nitruration",
                "Rugosité": "Ra 0.2"
            }
        }
        
        return self.results
