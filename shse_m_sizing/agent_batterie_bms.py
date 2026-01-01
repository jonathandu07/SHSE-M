from .agent_base import Agent

class BatteryAgent(Agent):
    """
    Battery and BMS sizing.
    """
    def __init__(self, config, I_charge_A):
        super().__init__(config, "BatteryAgent")
        self.I_charge = I_charge_A

    def run(self):
        self.log("Starting battery sizing...")
        cap_kWh = self.config['subsystems']['battery']['capacity_kWh']
        V_nom = self.config['subsystems']['battery']['voltage_nominal_V']
        
        # Capacity Ah
        cap_Ah = (cap_kWh * 1000.0) / V_nom
        self.results['capacity_Ah'] = cap_Ah
        
        # C-Rate Check
        C_rate_charging = self.I_charge / cap_Ah
        self.results['charging_C_rate'] = C_rate_charging
        self.log(f"Battery Capacity: {cap_Ah:.1f} Ah")
        self.log(f"Charging C-Rate: {C_rate_charging:.2f} C")
        
        if C_rate_charging > 3.0:
            self.warn(f"High charging C-rate: {C_rate_charging:.2f}C")
            
        return self.results
