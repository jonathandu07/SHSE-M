from .agent_base import Agent

class EfficiencyAgent(Agent):
    """
    Calculates the required shaft power and indicated power based on the battery target.
    Equation: eta_global = eta_th * eta_m * eta_gen * eta_elec * eta_charge
    P_shaft = P_batt / (eta_gen * eta_elec * eta_charge)
    """
    def __init__(self, config):
        super().__init__(config, "EfficiencyAgent")

    def run(self):
        self.log("Starting efficiency analysis...")
        
        # Inputs
        P_batt = self.config['input']['P_batt_target_kW']
        eta_gen = self.config['efficiencies']['eta_gen']
        eta_elec = self.config['efficiencies']['eta_elec']
        eta_charge = self.config['efficiencies']['eta_charge']
        eta_m = self.config['efficiencies']['eta_m']
        
        # Validate inputs
        self.check(0.0 < eta_gen <= 1.0, "Generator efficiency must be between 0 and 1")
        self.check(0.0 < eta_elec <= 1.0, "Electronics efficiency must be between 0 and 1")
        
        # 1. Electrical Chain Efficiency
        eta_elec_chain = eta_gen * eta_elec * eta_charge
        self.results['eta_elec_chain'] = eta_elec_chain
        
        # 2. Shaft Power Requirement
        # P_batt = P_shaft * eta_elec_chain
        P_shaft = P_batt / eta_elec_chain
        self.results['P_shaft_kW'] = P_shaft
        self.log(f"Target Battery Power: {P_batt} kW")
        self.log(f"Electrical Chain Efficiency: {eta_elec_chain:.3f}")
        self.log(f"Required Shaft Power: {P_shaft:.3f} kW")
        
        # 3. Indicated Power Requirement
        # P_shaft = P_indicated * eta_m
        P_indicated = P_shaft / eta_m
        self.results['P_indicated_kW'] = P_indicated
        self.log(f"Mechanical Efficiency: {eta_m}")
        self.log(f"Required Indicated Power: {P_indicated:.3f} kW")
        
        return self.results
