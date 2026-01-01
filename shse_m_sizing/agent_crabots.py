import math
from .agent_base import Agent

class DogClutchAgent(Agent):
    """
    Sizing of the Dog Clutch (Boîte à Crabots).
    """
    def __init__(self, config, Torque_max_Nm):
        super().__init__(config, "DogClutchAgent")
        self.Torque = Torque_max_Nm

    def run(self):
        self.log("Starting dog clutch sizing...")
        params = self.config['subsystems']['dog_clutch']
        
        n = params['n_teeth']
        rm = params['mean_radius_mm'] / 1000.0
        h = params['tooth_height_mm'] / 1000.0
        mu = params['friction_coeff']
        
        # 1. Tangential Force
        # T = Ft * rm
        Ft = self.Torque / rm
        self.log(f"Tangential Force: {Ft:.1f} N")
        
        # 2. Contact Pressure
        # Area ~ n * (rm_out - rm_in) * contact_depth?
        # Simplify: Area ~ n * h * (width?)
        # Let's assume width b
        b = 0.015 # 15mm width Assumption/Default
        
        Area_contact = n * h * b
        P_contact = Ft / Area_contact
        
        self.results['contact_pressure_MPa'] = P_contact / 1e6
        self.log(f"Contact Pressure: {P_contact/1e6:.1f} MPa")
        
        # Warning if high
        if P_contact > 200e6: # 200 MPa limit for steel roughly (surface)
            self.warn("High contact pressure on dog teeth!")

        # 3. Shear Stress
        # Area_shear = n * b * (length_arc?)
        # Approx Arc length ~ 2*pi*rm / (2*n) (50% duty)
        arc_len = (2 * math.pi * rm) / (2 * n)
        Area_shear = n * b * arc_len
        Tau_shear = Ft / Area_shear
        
        self.results['shear_stress_MPa'] = Tau_shear / 1e6
        
        # 4. Self-Locking / Back-taper
        # Need tan(alpha) < mu to hold? Or > mu to release? 
        # Typically back-taper prevents disengagement.
        # Here just logging the friction capability.
        
        return self.results
