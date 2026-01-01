import math
from .agent_base import Agent

class ThermodynamicAgent(Agent):
    """
    Dimensions the engine geometry (Bore, Stroke, Volume) based on power requirements and MEP.
    """
    def __init__(self, config, P_indicated_kW):
        super().__init__(config, "ThermodynamicAgent")
        self.P_indicated_kW = P_indicated_kW

    def run(self):
        self.log("Starting thermodynamic sizing...")
        
        # Inputs
        N_rpm = self.config['input']['N_rpm']
        p_me_target_bar = self.config['input']['p_me_target_bar']
        phi = self.config['input']['phi_ratio']
        T_hot = self.config['input']['T_hot_K']
        T_cold = self.config['input']['T_cold_K']
        
        # 1. Total Displacement
        # P_i (W) = p_me (Pa) * Vd (m3/s)
        # Vd_total (m3) = P_i * 60 / (p_me * N)
        p_me_Pa = p_me_target_bar * 1e5
        P_i_W = self.P_indicated_kW * 1000.0
        
        Vd_total = (P_i_W * 60.0) / (p_me_Pa * N_rpm)
        self.results['Vd_total_cc'] = Vd_total * 1e6
        self.log(f"Total Displacement Required: {self.results['Vd_total_cc']:.1f} cc")
        
        # 2. Geometry & Cylinder Optimization
        # Iterate N_cyl from 1 to 6 to find optimal configuration
        # Criteria: Keep Mass < Max and Stress < Limit
        # Preference: Maximize N_cyl for longevity (lower unit load) WITHIN mass/volume limits.
        
        max_weight = self.config['constraints'].get('max_system_weight_kg', 50.0)
        best_N = 1
        best_score = -1e9
        
        candidates = []
        
        for N in range(1, 7):
            # Unit Displacement
            Vd_unit = Vd_total / N
            
            # Dimensions (Square)
            Bore = (Vd_unit * 4.0 / math.pi)**(1.0/3.0)
            Stroke = Bore
            
            # Est. Unit Mass Breakdown (Rough scaling)
            # Piston ~ B^3
            # Rod ~ N/A
            # Liner/Block ~ B^2 * S
            # Fixed Overhead (Accessories) ~ 5kg + 1kg/cyl
            
            # Simple Mass Model:
            # Vol_mat ~ Vd_unit * 5 (Block factor) * Density_Alu
            rho_alu = 2700.0
            mass_unit_eng = (Vd_unit * 5.0) * rho_alu 
            mass_moving = (Vd_unit * 1.5) * 7800.0 # Steel parts approx
            
            mass_per_cyl = mass_unit_eng + mass_moving
            mass_fixed = 10.0 # Alternator, casing, electronics base
            
            total_mass = mass_fixed + (mass_per_cyl * N)
            
            # Stress Indicator (Force per piston)
            p_max_Pa = (p_me_target_bar / phi) * 1e5
            Area = math.pi * Bore**2 / 4
            F_max = p_max_Pa * Area
            
            # Score: Higher N is better for longevity, BUT must be valid
            # Score: Weighted combination
            # 1. Longevity (Force per piston): Lower is better.
            # 2. Cost/Complexity: Lower N is better.
            # 3. Volume Logic: Prefer 300cc - 600cc per cyl (Automotive Standard).
            
            # Penalties
            # P_mass = 1 if mass > max_weight else 0
            
            # Normalized Metrics (approx)
            norm_force = F_max / 15000.0 # 1 cyl is ~15kN
            norm_cost = N / 6.0 
            
            # Volume Check
            vol_penalty = 0
            if Vd_unit < 200: vol_penalty = 0.5 # Too small (Friction high relative to power)
            if Vd_unit > 800: vol_penalty = 0.2 # Too big (Vibration)
            
            # Score formula (Higher is better)
            # We want Low Force (Longevity) but Low Cost.
            # Let's say: Score = (1 - norm_force)*0.6 + (1 - norm_cost)*0.4 - vol_penalty
            # Actually simplest: 
            #   Maximize N for longevity, BUT subtract penalty for N cost.
            
            score = (N * 10) - (N * N * 1.5) # Diminishing returns on N
            # 1: 10 - 1.5 = 8.5
            # 2: 20 - 6 = 14
            # 3: 30 - 13.5 = 16.5
            # 4: 40 - 24 = 16
            # 5: 50 - 37.5 = 12.5
            # 6: 60 - 54 = 6
            
            # Add Mass constraint hard stop
            if total_mass > max_weight:
                score = -1000
                
            candidates.append((N, total_mass, F_max, score, Bore, Stroke))
            
            if score > best_score:
                best_score = score
                best_N = N
            else:
                 self.log(f"   N={N}: Mass={total_mass:.1f}, Score={score:.1f}")

        # Fallback if no candidate
        if not candidates:
            self.warn("No cylinder count met mass constraints! Defaulting to 1.")
            best_N = 1
            Vd_unit = Vd_total
            Bore = (Vd_unit * 4.0 / math.pi)**(1.0/3.0)
            Stroke = Bore
            total_mass = 99.9
            F_max = (p_me_target_bar/phi)*1e5 * (math.pi*Bore**2/4)
        else:
            # Retrieve Best
            for c in candidates:
                if c[0] == best_N:
                    _, total_mass, F_max, _, Bore, Stroke = c
                    break
        
        self.results['N_cylinders'] = best_N
        self.results['Bore_mm'] = Bore * 1000.0
        self.results['Stroke_mm'] = Stroke * 1000.0
        self.results['Est_System_Mass_kg'] = total_mass
        self.results['Max_Force_Per_Piston_N'] = F_max
        
        # Store optimization candidates for Report
        self.results['optimization_candidates'] = candidates # [(N, Mass, Force, Score, B, S)]
        
        self.log(f"OPTIMIZATION RESULT: {best_N} Cylinders")
        self.log(f"   > Bore/Stroke: {self.results['Bore_mm']:.1f} mm")
        self.log(f"   > Est. Mass: {total_mass:.1f} kg (Limit: {max_weight})")
        self.log(f"   > Unit Force: {F_max:.0f} N")
        
        # 3. Mean Piston Speed Verification
        # U_p = 2 * S * N / 60
        U_p = 2.0 * Stroke * N_rpm / 60.0
        self.results['U_mean_m_s'] = U_p
        
        U_p_max = self.config['constraints']['U_p_max_m_s']
        self.check(U_p <= U_p_max, f"Mean Piston Speed {U_p:.2f} m/s exceeds limit {U_p_max} m/s")
        self.log(f"Mean Piston Speed: {U_p:.2f} m/s (Limit: {U_p_max})")
        
        # 4. Max Pressure Estimation
        # p_max = p_me / phi
        p_max_bar = p_me_target_bar / phi
        self.results['p_max_bar'] = p_max_bar
        self.results['p_max_Pa'] = p_max_bar * 1e5
        self.log(f"Estimated Max Pressure: {p_max_bar:.1f} bar")
        
        # 5. Carnot & Thermal Efficiency
        eta_carnot = 1.0 - (T_cold / T_hot)
        eta_cycle_factor = self.config['efficiencies']['eta_carnot_factor']
        eta_th = eta_carnot * eta_cycle_factor
        
        self.results['eta_carnot'] = eta_carnot
        self.results['eta_th'] = eta_th
        self.log(f"Carnot Efficiency: {eta_carnot:.3f} (Th={T_hot}K, Tc={T_cold}K)")
        self.log(f"Estimated Thermal Efficiency: {eta_th:.3f} (Factor={eta_cycle_factor})")

        return self.results
