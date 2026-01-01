import csv
import json
from .agent_base import Agent

class BOMAgent(Agent):
    """
    Generates Bill of Materials.
    """
    def __init__(self, config, all_results):
        super().__init__(config, "BOMAgent")
        self.all_results = all_results

    def run(self):
        self.log("Generating BOM...")
        bom = []
        
        # 1. Cylinder
        thermo = self.all_results.get('ThermodynamicAgent', {})
        if thermo:
            bom.append({
                "Part": "Cylinder Liner",
                "Spec": f"Bore {thermo.get('Bore_mm',0):.1f}mm",
                "Qty": self.config['input'].get('N_cyl', 1),
                "Material": self.config['constraints']['mat_cylinder']
            })
            
        # 2. Piston
        mech = self.all_results.get('MechanicalAgent', {})
        if mech:
            bom.append({
                "Part": "Power Piston",
                "Spec": f"Dia {mech.get('piston_diameter', thermo.get('Bore_mm',0)):.1f}mm",
                "Qty": self.config['input'].get('N_cyl', 1),
                "Material": self.config['constraints']['mat_piston']
            })
            bom.append({
                "Part": "Connecting Rod",
                "Spec": f"L={mech.get('rod_length_mm',0):.1f}mm",
                "Qty": self.config['input'].get('N_cyl', 1),
                "Material": self.config['constraints']['mat_rod']
            })

        self.results['BOM_List'] = bom
        return self.results

    def export_csv(self, filename):
        bom = self.results.get('BOM_List', [])
        if not bom:
            return
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["Part", "Spec", "Qty", "Material"])
            writer.writeheader()
            writer.writerows(bom)
        self.log(f"BOM exported to {filename}")
