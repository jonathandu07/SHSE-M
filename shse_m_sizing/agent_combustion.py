from .agent_base import Agent

class CombustionAgent(Agent):
    """
    Calculates fuel requirements and heat input.
    """
    def __init__(self, config, P_indicated_kW, eta_th):
        super().__init__(config, "CombustionAgent")
        self.P_indicated_kW = P_indicated_kW
        self.eta_th = eta_th

    def run(self):
        self.log("Starting combustion analysis...")
        
        # 1. Heat Input Required
        # P_th_in = P_indicated / eta_th  (Wait, P_ind is work output of cycle)
        # Actually P_shaft = P_th_in * eta_th * eta_m
        # So P_indicated = P_th_in * eta_th
        P_th_in_kW = self.P_indicated_kW / self.eta_th
        self.results['P_thermal_input_kW'] = P_th_in_kW
        self.log(f"Required Thermal Input: {P_th_in_kW:.2f} kW")
        
        # 2. Fuel Consumption
        # m_dot_fuel = P_th_in / (LHV * eta_comb)
        # LHV Gasoline approx 44 MJ/kg = 44000 kJ/kg
        LHV_kJ_kg = 44000.0 
        eta_comb = self.config['efficiencies']['eta_combustion']
        
        m_dot_fuel_kg_s = P_th_in_kW / (LHV_kJ_kg * eta_comb)
        m_dot_fuel_g_s = m_dot_fuel_kg_s * 1000.0
        m_dot_fuel_kg_h = m_dot_fuel_kg_s * 3600.0
        
        self.results['fuel_consumption_kg_h'] = m_dot_fuel_kg_h
        self.results['fuel_consumption_g_s'] = m_dot_fuel_g_s
        self.log(f"Fuel Consumption: {m_dot_fuel_kg_h:.3f} kg/h")
        
        # 3. Mass Flow of Air (Approx for Injector/Intake)
        # AFR (Stoichiometric) ~ 14.7 for Gasoline
        AFR = 14.7
        m_dot_air_kg_s = m_dot_fuel_kg_s * AFR
        self.results['air_flow_kg_s'] = m_dot_air_kg_s
        self.log(f"Air Flow: {m_dot_air_kg_s*3600:.2f} kg/h")
        
        return self.results
