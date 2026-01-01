import csv
import json
import dataclasses
from typing import Any
from .config import InputParameters, DimensionResults

def generate_markdown_report(inputs: InputParameters, res: DimensionResults, filename: str = "report.md"):
    md = f"""# Rapport de Dimensionnement SHSE-M

## 1. Hypothèses et Entrées
- **Puissance Batterie Cible**: {inputs.P_batt_target} kW
- **Régime**: {inputs.N_rpm} tr/min
- **Fluide**: {inputs.fluid}
- **Pression Moyenne (MEP) Target**: {inputs.p_me_target_bar} bar
- **Ratio S/B**: {inputs.limits.S_over_B}
- **Rendements**: 
  - Thermique: {inputs.eta.eta_th}
  - Méca: {inputs.eta.eta_m}
  - Générateur: {inputs.eta.eta_gen}
  - Élec: {inputs.eta.eta_elec}
  - Charge: {inputs.eta.eta_charge}
  - **Global**: {inputs.eta.eta_global:.3f}

## 2. Résultats Principaux
| Paramètre | Valeur | Unité |
|-----------|--------|-------|
| Puissance Arbre requise | {res.P_shaft_req/1000.0:.2f} | kW |
| Puissance Indiquée | {res.P_indications_req/1000.0 if hasattr(res, 'P_indications_req') else res.P_indicated_req/1000.0:.2f} | kW |
| Alésage (Bore) | {res.Bore*1000:.1f} | mm |
| Course (Stroke) | {res.Stroke*1000:.1f} | mm |
| Cylindrée Totale | {res.Vd_total*1e6:.0f} | cm3 |
| Vitesse Piston Moyenne | {res.U_mean:.2f} | m/s |
| Pression Max Cycle | {res.p_max/1e5:.1f} | bar |
| Force Max Piston | {res.F_max:.0f} | N |

## 3. Dimensionnement Composants
- **Épaisseur Paroi Cylindre**: {res.wall_thickness*1000:.2f} mm (Alu + SF={inputs.limits.safety_factor})
- **Diamètre Bielle (Est.)**: {res.rod_diameter*1000:.1f} mm
- **Longueur Bielle**: {res.rod_length*1000:.1f} mm
- **Diamètre Maneton**: {res.pin_diameter*1000:.1f} mm
- **Volant Inertie**:
  - Inertie: {res.flywheel_inertia:.3f} kg.m²
  - Masse: {res.flywheel_mass:.2f} kg
  - Diamètre: {res.flywheel_diameter*1000:.0f} mm

## 4. Vérifications et Alertes
"""
    if not res.warnings:
        md += "- Aucun avertissement critique.\n"
    else:
        for w in res.warnings:
            md += f"- **{w}**\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)

def generate_bom_csv(res: DimensionResults, filename: str = "bom.csv"):
    rows = [
        ["Composant", "Dimension Principale", "Valeur", "Unité", "Matériau Suggéré", "Notes"],
        ["Cylindre", "Alésage", f"{res.Bore*1000:.1f}", "mm", "Aluminium/Fonte", "Chemisage possible"],
        ["Cylindre", "Course", f"{res.Stroke*1000:.1f}", "mm", "-", "-"],
        ["Cylindre", "Ép. Paroi", f"{res.wall_thickness*1000:.2f}", "mm", "Aluminium", f"Calculé pour {res.p_max/1e5:.0f} bar"],
        ["Piston", "Diamètre", f"{res.Bore*1000:.1f}", "mm", "Alu Haute Temp", "-"],
        ["Bielle", "Entraxe", f"{res.rod_length*1000:.1f}", "mm", "Acier Forgé", "-"],
        ["Bielle", "Diamètre Corps", f"{res.rod_diameter*1000:.1f}", "mm", "Acier Forgé", "Section circulaire equiv."],
        ["Vilebrequin", "Rayon Manivelle", f"{res.crank_radius*1000:.1f}", "mm", "Acier", "-"],
        ["Vilebrequin", "Diamètre Maneton", f"{res.pin_diameter*1000:.1f}", "mm", "Acier Traité", "Surface rectifiée"],
        ["Volant", "Diamètre Ext.", f"{res.flywheel_diameter*1000:.0f}", "mm", "Acier/Fonte", f"Masse ~{res.flywheel_mass:.1f} kg"],
        ["Alternateur", "Puissance Nom.", f"{res.P_shaft_req/1000.0:.2f}", "kW", "-", "Accouplement direct ou courroie"]
    ]
    
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

class EnhancedJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if dataclasses.is_dataclass(o):
                return dataclasses.asdict(o)
            return super().default(o)

def generate_json_export(inputs: InputParameters, res: DimensionResults, filename: str = "params.json"):
    data = {
        "inputs": inputs,
        "results": res
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, cls=EnhancedJSONEncoder, indent=4)
