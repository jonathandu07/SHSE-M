import os
import csv
import json
import dataclasses
from typing import Any
from .config import InputParameters, DimensionResults

def generate_markdown_report(inputs: InputParameters, res: DimensionResults, filename: str = "report.md"):
    # (Existing text generation omitted for brevity, we reconstruct the string)
    md = f"""# Rapport de Dimensionnement SHSE-M

## 1. Hypothèses et Entrées
- **Puissance Batterie Cible**: {inputs.P_batt_target} kW
- **Régime**: {inputs.N_rpm} tr/min
- **Fluide**: {inputs.fluid}
- **Pression Moyenne**: {inputs.p_me_target_bar} bar
- **Rendement Global**: {inputs.eta.eta_global:.3f}

## 2. Résultats Géométrie
| Paramètre | Valeur | Unité |
|-----------|--------|-------|
| Alésage (B) | {res.Bore*1000:.1f} | mm |
| Course (S) | {res.Stroke*1000:.1f} | mm |
| Cylindrée | {res.Vd_total*1e6:.0f} | cm3 |
| Vit. Piston | {res.U_mean:.2f} | m/s |
| Force Max | {res.F_max:.0f} | N |

## 3. Détail des Pièces Calculées (Extrait)
Voir `bom.csv` pour la liste exhaustive.

### Piston & Segments
- **Diamètre**: {res.piston_diameter*1000:.1f} mm
- **Axe**: Ø{res.pin_diameter*1000:.1f} x {res.pin_length*1000:.1f} mm
- **Segments**: {res.num_rings} x (H={res.ring_height*1000:.2f} mm)

### Bielle
- **Entraxe**: {res.rod_length*1000:.1f} mm
- **Pied**: Ø{res.rod_small_end_diameter*1000:.1f} mm
- **Tête**: Ø{res.rod_big_end_diameter*1000:.1f} mm
- **Vis de Bielle**: M{res.rod_bolt_diameter*1000:.0f} (est.)

### Vilebrequin
- **Maneton**: Ø{res.crank_pin_diameter*1000:.1f} x {res.crank_pin_length*1000:.1f} mm
- **Tourillon**: Ø{res.main_journal_diameter*1000:.1f} mm
- **Recouvrement**: {res.overlap*1000:.1f} mm

## 4. Croquis Techniques
"""
    # Insert Images
    if res.sketch_paths:
        for path in res.sketch_paths:
            # Use relative path for markdown if possible, else absolute
            rel_path = os.path.basename(path) 
            md += f"![Croquis]({rel_path})\n\n"

    md += "## 5. Vérifications\n"
    if not res.warnings:
        md += "- Aucun avertissement majeur.\n"
    else:
        for w in res.warnings:
            md += f"- **{w}**\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(md)

def generate_bom_csv(res: DimensionResults, filename: str = "bom.csv"):
    rows = [
        ["Systeme", "Composant", "Détail", "Valeur", "Unité", "Matériau", "Commentaire"],
        # Bloc
        ["Bloc", "Cylindre", "Alésage", f"{res.Bore*1000:.2f}", "mm", "Fonte/Alu", "Chemisé"],
        ["Bloc", "Chemise", "Épaisseur", f"{res.wall_thickness*1000:.2f}", "mm", "Acier", "Calcul Pression Max"],
        ["Bloc", "Goujons Culasse", "Diamètre", f"{res.head_bolt_diameter*1000:.1f}", "mm", "Acier 12.9", f"{res.num_head_bolts} vis"],
        # Piston
        ["Attelage", "Piston", "Diamètre", f"{res.piston_diameter*1000:.2f}", "mm", "Alu Forgé", "-"],
        ["Attelage", "Piston", "Hauteur Totale", f"{res.piston_height*1000:.1f}", "mm", "-", "-"],
        ["Attelage", "Piston", "Hauteur Comp.", f"{res.piston_compression_height*1000:.1f}", "mm", "-", "Axe à Calotte"],
        ["Attelage", "Axe Piston", "Diamètre", f"{res.pin_diameter*1000:.2f}", "mm", "Acier Cémenté", "-"],
        ["Attelage", "Axe Piston", "Longueur", f"{res.pin_length*1000:.1f}", "mm", "-", "-"],
        ["Attelage", "Segments", "Hauteur", f"{res.ring_height*1000:.2f}", "mm", "Fonte", f"{res.num_rings} segments"],
        # Bielle
        ["Attelage", "Bielle", "Entraxe", f"{res.rod_length*1000:.1f}", "mm", "Acier Forgé", "Lambda variable"],
        ["Attelage", "Bielle", "Pied (Oeil)", f"{res.rod_small_end_diameter*1000:.1f}", "mm", "-", "Bagué bronze"],
        ["Attelage", "Bielle", "Tête (Alésage)", f"{res.rod_big_end_diameter*1000:.1f}", "mm", "-", "Avec coussinets"],
        ["Attelage", "Bielle", "Corps (Largeur)", f"{res.rod_column_section_width*1000:.1f}", "mm", "-", "Section I"],
        ["Attelage", "Vis Bielle", "Diamètre", f"{res.rod_bolt_diameter*1000:.1f}", "mm", "Acier 12.9", "2 vis par bielle"],
        # Vilebrequin
        ["Bas Moteur", "Vilebrequin", "Course", f"{res.Stroke*1000:.1f}", "mm", "Acier Forgé", "-"],
        ["Bas Moteur", "Maneton", "Diamètre", f"{res.crank_pin_diameter*1000:.1f}", "mm", "Traîté", "Rectifié"],
        ["Bas Moteur", "Maneton", "Longueur", f"{res.crank_pin_length*1000:.1f}", "mm", "-", "-"],
        ["Bas Moteur", "Tourillon", "Diamètre", f"{res.main_journal_diameter*1000:.1f}", "mm", "-", "Palier Lisse"],
        ["Bas Moteur", "Bras", "Épaisseur", f"{res.web_thickness*1000:.1f}", "mm", "-", "-"],
        # Volant
        ["Transmission", "Volant", "Diamètre", f"{res.flywheel_diameter*1000:.0f}", "mm", "Acier", "-"],
        ["Transmission", "Volant", "Largeur", f"{res.flywheel_width*1000:.1f}", "mm", "-", "Jante"],
        ["Transmission", "Volant", "Masse", f"{res.flywheel_mass:.2f}", "kg", "-", f"Inertie {res.flywheel_inertia:.3f}"],
        # Periph
        ["Refroidissement", "Water Jacket", "Surface", f"{res.water_jacket_area*1e4:.0f}", "cm2", "-", "Estimation"],
        ["Electrique", "Alternateur", "Couple Nom.", f"{res.Torque_mean:.1f}", "Nm", "-", "-"]
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
