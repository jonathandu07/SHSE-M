from .agent_base import Agent

class CaptiveGasAgent(Agent):
    """
    Models the Cold Chamber / Buffer Gas.
    """
    def __init__(self, config, Vd_total_cc):
        super().__init__(config, "CaptiveGasAgent")
        self.V_displaced = Vd_total_cc * 1e-6 # Convert cc to m3

    def run(self):
        self.log("Starting captive gas sizing...")
        # Assumption: Cold chamber volume should be significantly larger than displaced volume 
        # to behave as a buffer (or nearly equal if acting as a bounce chamber).
        # In this architecture, let's assume it accommodates the displacement with a pressure rise.
        
        # V_dead = V_clearance + V_buffer
        # Let's say we want pressure variation < 20%? Or is it part of the cycle?
        # User defined: "Gaz captif, valve remplissage, soupape surpression"
        
        # Let's size the cold volume to be X times the stroke volume.
        # This is a design parameter. Let's pick 1.5x for now.
        V_cold_mean = self.V_displaced * 2.0 
        
        self.results['V_cold_mean_liter'] = V_cold_mean * 1000.0
        
        # P0, T0
        P_charge_bar = 5.0 # Pre-charge pressure? Hypothesis.
        T_cold = self.config['input']['T_cold_K']
        
        # Mass of gas
        # PV = mRT
        # R for Nitrogen ~ 297 J/kgK
        R_gas = 297.0
        P_charge_Pa = P_charge_bar * 1e5
        
        m_gas = (P_charge_Pa * V_cold_mean) / (R_gas * T_cold)
        self.results['mass_gas_g'] = m_gas * 1000.0
        
        # Max Pressure estimation in cold buffer (Isothermal or Polytropic?)
        # P1 * V1^k = P2 * V2^k
        # V_min = V_mean - Vd/2 ? (Depending on kinematics)
        # Simplified Check for safety valve
        P_max_buffer = P_charge_bar * (V_cold_mean / (V_cold_mean - 0.5*self.V_displaced))**1.4
        
        self.results['P_max_buffer_bar'] = P_max_buffer
        self.log(f"Cold Buffer Volume: {self.results['V_cold_mean_liter']:.2f} L")
        self.log(f"Gas Mass (N2): {self.results['mass_gas_g']:.2f} g")
        self.log(f"Est. Max Buffer Pressure: {P_max_buffer:.2f} bar")
        
        return self.results
