import math
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pieces._base_piece import BasePiece

class Piece(BasePiece):
    def __init__(self):
        super().__init__()
        self.name = "Vilebrequin (Crankshaft)"
        self.ref = "MEC-002"
        self.category = "MECANIQUE"
        self.description = "Vilebrequin assemblé ou forgé. Dimensionné en torsion et fatigue."

    def dimensionner(self, cyl, bie, n_cyl):
        """
        Dimensionnement Torsion / Flexion.
        """
        self.inputs = {
            "Couple Moyen (Nm)": 0,
            "Couple Crête (Nm)": 0,
            "Contrainte Torsion (MPa)": 0,
            "Facteur Sécurité (Fatigue)": 0
        }

        # 1. CHARGES
        # On estime le couple moyen via la P_meca
        # On n'a pas P_meca direct ici, on l'estime via cyl.cylindree
        # P approx = Bn * P_mean * V * f
        # Torque = P / w
        # Simplification : On recupère la force bielle max et le bras de levier
        force_bielle_max_n = bie.force_compression_max_n
        bras_levier_m = cyl.course_m / 2.0
        
        # Couple instantané max (pire cas : bielle tangente 90°)
        torque_peak_nm = force_bielle_max_n * bras_levier_m
        
        # 2. DIMENSIONNEMENT TOURILLONS & MANETONS
        # Maneton : 0.60 * Stroke (Rigidité)
        diam_maneton_m = cyl.course_m * 0.60
        # Tourillon : 0.65 * Stroke
        diam_tourillon_m = cyl.course_m * 0.65
        
        # 3. VERIFICATION TORSION
        # Tau = 16 * T / (pi * d^3)
        tau_torsion_pa = (16 * torque_peak_nm) / (math.pi * diam_tourillon_m**3)
        tau_torsion_mpa = tau_torsion_pa / 1e6
        
        # 4. MATÉRIAU & SÉCURITÉ
        MAT_RE_MPA = 900.0 # 42CrMo4
        TAU_ADMISSIBLE = MAT_RE_MPA * 0.58 # Critère Von Mises cisaillement
        FS_TORSION = TAU_ADMISSIBLE / tau_torsion_mpa
        
        # 5. RÉSULTATS
        self.inputs["Couple Crête (Nm)"] = round(torque_peak_nm, 1)
        self.inputs["Contrainte Torsion (MPa)"] = round(tau_torsion_mpa, 2)
        self.inputs["Facteur Sécurité (Fatigue)"] = round(FS_TORSION, 1)
        
        self.dimensions = {
            "Diam_Maneton_mm": diam_maneton_m * 1000.0,
            "Larg_Maneton_mm": bie.dimensions["Largeur_Corps_mm"] + 5.0, # Jeu latéral
            "Diam_Tourillon_mm": diam_tourillon_m * 1000.0,
            "Longueur_Totale_mm": (1.5 * cyl.alesage_m * n_cyl + 0.2) * 1000.0
        }
        
        self.materiau = "Acier Forgé 42CrMo4"
        self.masse_estimee_kg = n_cyl * 15.0 * (cyl.cylindree_unitaire_m3 * 1000.0) # Heuristique 15kg/litre
        self.cout_estime_euro = 500.0 * n_cyl
        
        # Output variables for other modules
        self.diametre_tourillon_m = diam_tourillon_m
        self.couple_max_approx_nm = torque_peak_nm
