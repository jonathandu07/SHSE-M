import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os
from .agent_base import Agent

class GraphiqueAgent(Agent):
    """
    Generates scientific engineering plots: PV Diagrams, Kinematics.
    """
    def __init__(self, config, all_results):
        super().__init__(config, "GraphiqueAgent")
        self.data = all_results

    def run(self):
        self.log("Generating technical graphs...")
        output_dir = "output_shse_m" # Fixed output dir for now
        
        thermo = self.data.get('ThermodynamicAgent', {})
        
        if not thermo:
            self.warn("No thermodynamic data for graphs.")
            return {}

        B = thermo.get('Bore_mm', 0) / 1000.0
        S = thermo.get('Stroke_mm', 0) / 1000.0
        Vd = thermo.get('Vd_total_cc', 0) * 1e-6
        p_max = thermo.get('p_max_Pa', 0)
        
        # 1. P-V Diagram (Idealized Stirling/Otto hybrid)
        # Volume array
        theta = np.linspace(0, 720, 360) # 2 rotations (though Stirling is cycle per rot usually? depends on config)
        # Let's assume standard V(theta)
        # V = Vc + (Vd/2)*(1 - cos(theta))
        Vc = Vd / (10.0 - 1.0) # CR = 10 assumption
        
        rads = np.radians(theta)
        vol_profile = Vc + (Vd/2.0) * (1.0 - np.cos(rads))
        
        # Pressure (Ideal Gas P*V^k = C)
        # Simplified cycle: 
        # Compression (0-180), Expansion (180-360)... 
        # This is dummy physics for visualization unless we implement real cycle integration.
        # Using a synthetic curve that looks like a cycle.
        pressure_profile = []
        for v in vol_profile:
            # Fake polytropic
            pressure_profile.append(p_max * (Vc/v)**1.3)
            
        fig1, ax1 = plt.subplots(figsize=(6, 4))
        ax1.plot(vol_profile * 1e6, np.array(pressure_profile)/1e5, color='b', linewidth=2)
        ax1.set_title("Diagramme P-V (Théorique)")
        ax1.set_xlabel("Volume (cc)")
        ax1.set_ylabel("Pression (bar)")
        ax1.grid(True, linestyle='--', alpha=0.7)
        
        path1 = os.path.join(output_dir, "graph_pv.png")
        fig1.savefig(path1)
        plt.close(fig1)
        
        self.results['path_graph_pv'] = path1
        
        # 2. Piston Velocity
        # U = w * r * sin(theta)
        rpm = self.config['input']['N_rpm']
        w = 2 * np.pi * rpm / 60.0
        r = S / 2.0
        
        velocity = w * r * np.sin(rads)
        
        fig2, ax2 = plt.subplots(figsize=(6, 4))
        ax2.plot(theta, velocity, color='r')
        ax2.set_title("Vitesse Piston")
        ax2.set_xlabel("Angle Vilebrequin (°)")
        ax2.set_ylabel("Vitesse (m/s)")
        ax2.grid(True)
        
        path2 = os.path.join(output_dir, "graph_vitesse.png")
        fig2.savefig(path2)
        plt.close(fig2)
        
        self.results['path_graph_vitesse'] = path2
        
        return self.results
