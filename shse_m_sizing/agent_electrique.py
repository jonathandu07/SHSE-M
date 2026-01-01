from .agent_base import Agent

class ElectricalAgent(Agent):
    """
    Sizing of Alternator, Rectifier, Cabling.
    """
    def __init__(self, config, P_shaft_kW):
        super().__init__(config, "ElectricalAgent")
        self.P_shaft = P_shaft_kW

    def run(self):
        self.log("Starting electrical sizing...")
        # 1. Alternator Sizing
        # P_elec = P_shaft * eta_gen
        eta_gen = self.config['efficiencies']['eta_gen']
        P_nom = self.P_shaft * eta_gen
        
        self.results['alternator_power_kW'] = P_nom
        
        # 2. Rectifier / Bus DC
        V_bus = self.config['subsystems']['battery']['voltage_nominal_V']
        I_max = (P_nom * 1000.0) / V_bus
        
        self.results['current_max_A'] = I_max
        self.log(f"Alternator Power: {P_nom:.1f} kW")
        self.log(f"Bus Current: {I_max:.1f} A (@{V_bus}V)")
        
        # 3. Cabling
        # Rule of thumb: 4-5 A/mm2
        cable_section = I_max / 4.0
        self.results['cable_section_mm2'] = cable_section
        self.log(f"Recommended Cable Section: {cable_section:.1f} mm2")
        
        return self.results
