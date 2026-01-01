from .agent_base import Agent

class CoolingAgent(Agent):
    """
    Sizing of the cooling system.
    """
    def __init__(self, config, P_thermal_input_kW, P_indicated_kW):
        super().__init__(config, "CoolingAgent")
        self.Q_in = P_thermal_input_kW
        self.P_work = P_indicated_kW

    def run(self):
        self.log("Starting cooling system sizing...")
        # Heat Rejection
        # Q_reject = Q_in - P_work - Q_exhaust - Q_misc
        # Simplify: Q_reject ~ 30% of Q_in for ICE-like, maybe less for Stirling if regenerative?
        # But this is "combustion + récupération interne"
        # Let's assume balance:
        # P_work is ~ 30-40% 
        # Exhaust ~ 30%
        # Cooling ~ 30%
        
        Q_reject_kW = self.Q_in * 0.30
        self.results['heat_rejection_kW'] = Q_reject_kW
        self.log(f"Heat Rejection Target: {Q_reject_kW:.1f} kW")
        
        # Coolant Flow Rate
        # Q = m_dot * Cp * deltaT
        # Water/Glycol Cp ~ 3.5 kJ/kgK
        Cp_coolant = 3.5 
        deltaT = 10.0 # Standard radiator delta
        
        m_dot_coolant_kg_s = Q_reject_kW / (Cp_coolant * deltaT)
        self.results['coolant_flow_L_min'] = m_dot_coolant_kg_s * 60.0
        self.log(f"Coolant Flow: {self.results['coolant_flow_L_min']:.1f} L/min")
        
        return self.results
