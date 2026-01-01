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
        
        # 4. Synchronization Check (SHSE-M Requirement)
        # E_sync = 0.5 * J_eq * (Delta_omega)^2
        # We must enforce E_sync ~ 0.
        # Let's assume J_eq of the generator rotor is 0.05 kg.m2 (typical for PM)
        J_eq = 0.05 
        
        # Scenario: 50 RPM discrepancy (Bad sync)
        d_rpm_bad = 50.0
        d_omega_bad = d_rpm_bad * 2 * math.pi / 60.0
        E_sync_bad = 0.5 * J_eq * d_omega_bad**2
        
        # Safe Limit
        E_max_safe = 5.0 # Joules
        
        self.results['sync_energy_check_J'] = E_sync_bad
        
        if E_sync_bad > E_max_safe:
            self.warn(f"SHSE-M Warning: Dog Clutch MUST be synchronized! @50rpm delta, Energy={E_sync_bad:.1f}J")
        else:
            self.log("Sync Check: Energy manageable if Delta-RPM < 50.")
            
        self.results['shsem_components'] = {}
        self.results['shsem_components']['Crabots'] = {
            "name": "Système d'Accouplement",
            "material": "Acier 16MnCr5",
            "specs": [
                ("Type", f"{n} Dents"),
                ("Rayon Moyen", f"{rm*1000:.1f} mm"),
                ("Force Tang.", f"{Ft:.0f} N")
            ],
            "stress_data": [
                ("Pression Contact", f"{P_contact/1e6:.1f} MPa", "200.0"),
                ("Cisaillement", f"{Tau_shear/1e6:.1f} MPa", "400.0"),
                ("Sync Requise", "OUI", "DeltaW=0")
            ],
            "manufacturing": {
                "Dureté": "60 HRC",
                "Jeu Flanc": "0.1 mm"
            }
        }
        
        return self.results
