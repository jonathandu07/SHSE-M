import os

pieces_dir = os.path.join("backend", "pieces")

files_to_fix = [
    "brides_supports.py",
    "circlips_axe_piston.py",
    "contrepoids_equilibrage.py",
    "entretoises.py",
    "etancheite_paroi_mobile_joints_guide_labyrinthe_segments.py",
    "guidages_paroi_mobile_patins_bagues_glissieres.py",
    "huile_graisse.py",
    "jaquette_refroidissement_enveloppe_eau.py",
    "joint_tournant_arbre_sortie.py",
    "paliers_bielle_maneton.py",
    "systeme_rappel_precharge.py"
]

template = """import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    \"\"\"Modèle générique pour '{}'.\"\"\"

    def __init__(self):
        self.nom = "{}"

    def dimensionner(self, *args, **kwargs):
        \"\"\"Dimensionnement par défaut (Pass-through).\"\"\"
        pass

    def decrire(self) -> str:
        return f"Pièce: {{self.nom}} (Standard)"
"""

for fname in files_to_fix:
    path = os.path.join(pieces_dir, fname)
    if os.path.exists(path):
        name = fname[:-3]
        content = template.format(name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Fixed {fname}")
    else:
        print(f"File not found: {fname}")
