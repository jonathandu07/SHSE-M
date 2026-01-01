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
        
        # 2. Geometry (Bore/Stroke)
        # Assuming Square engine (B=S) initially or using config ratio if available
        # But user said "S max, B max" could be parameters. 
        # For this sizing, we'll iterate or pick a ratio.
        # Let's assume Stroke/Bore = 1.0 for simplicity unless constrained.
        R_sb = 1.0 
        # Vd = (pi/4) * B^2 * S = (pi/4) * B^3 * R_sb
        Bore = (Vd_total * 4.0 / (math.pi * R_sb))**(1.0/3.0)
        Stroke = Bore * R_sb
        
        self.results['Bore_mm'] = Bore * 1000.0
        self.results['Stroke_mm'] = Stroke * 1000.0
        self.log(f"Calculated Bore: {self.results['Bore_mm']:.2f} mm")
        self.log(f"Calculated Stroke: {self.results['Stroke_mm']:.2f} mm")
        
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
