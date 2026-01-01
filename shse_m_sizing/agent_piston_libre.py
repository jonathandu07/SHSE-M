import math
from .agent_base import Agent

class FreePistonAgent(Agent):
    """
    Sizing of the Free Piston (Séparateur Piston Libre).
    Critical Component for SHSE-M: Separates Hot Open Cycle from Cold Closed Cycle.
    Material: Ceramic (Si3N4) for thermal insulation and low mass.
    """
    def __init__(self, config, bore_mm):
        super().__init__(config, "FreePistonAgent")
        self.B = bore_mm / 1000.0 # m

    def run(self):
        self.log("Starting Free Piston sizing...")
        
        # 1. Geometry
        # "Cup" design to minimize conduction path and mass
        # Thickness t ~ 0.05 * B
        t_wall = 0.05 * self.B
        h_overall = 0.4 * self.B # Shorter than power piston
        
        self.results['free_piston_height_mm'] = h_overall * 1000
        self.results['free_piston_wall_thickness_mm'] = t_wall * 1000
        
        # 2. Material Properties (Si3N4 - Silicon Nitride)
        rho_si3n4 = 3200.0 # kg/m3
        k_cond = 30.0 # W/mK (relatively low for structural ceramic)
        
        # 3. Mass Estimation
        # Approx volume: Cylinder shell + bottom disk
        vol_shell = (math.pi * self.B * t_wall * h_overall)
        vol_disk = (math.pi * (self.B/2)**2 * t_wall)
        vol_total = vol_shell + vol_disk
        
        mass = vol_total * rho_si3n4
        self.results['free_piston_mass_kg'] = mass
        self.log(f"Free Piston Mass (Si3N4): {mass*1000:.1f} g")
        
        # 4. Thermal Insulation Check
        # Q_loss = k * A * dT / dx
        # This is critical for SHSE-M to prevent heating the cold gas
        A_cond = math.pi * (self.B/2)**2
        dT = 500.0 # Gradient assumption (950K -> 450K)
        dx = h_overall # Path length through the cup walls roughly
        
        Q_leak_cond = k_cond * (math.pi * self.B * t_wall) * dT / h_overall
        self.results['thermal_leak_conduction_W'] = Q_leak_cond
        self.log(f"Est. Thermal Leak (Conduction): {Q_leak_cond:.1f} W")
        
        # 5. Dynamics Check (Acceleration)
        # F = P * A. a = F / m.
        # Ensure it moves fast enough to follow pressure waves? 
        # Actually in SHSE-M it transmits pressure.
        # Low mass is good for responsiveness.
        
        # Output Component Data for GUI
        self.results['shsem_components'] = {}
        self.results['shsem_components']['Piston Libre'] = {
            "name": "Piston Libre (Séparateur)",
            "material": "Céramique Si3N4",
            "specs": [
                ("Diamètre", f"{self.B*1000:.1f} mm"),
                ("Hauteur", f"{h_overall*1000:.1f} mm"),
                ("Masse", f"{mass*1000:.1f} g"),
                ("Épaisseur paroi", f"{t_wall*1000:.1f} mm")
            ],
            "stress_data": [
                ("Fuite Thermique", f"{Q_leak_cond:.1f} W", "Minimiser")
            ],
            "manufacturing": {
                "Procédé": "Sintérisation",
                "Tolérance": "g6",
                "État Surface": "Rectifié Ra 0.2"
            }
        }
        
        return self.results
