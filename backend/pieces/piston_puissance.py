import math
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pieces._base_piece import BasePiece

class Piece(BasePiece):
    def __init__(self):
        super().__init__()
        self.name = "Piston De Puissance"
        self.ref = "MEC-010"
        self.category = "MECANIQUE"
        self.description = "Piston de compression/détente. Dimensionné au matage de l'axe."

    def dimensionner(self, cyl, regime_tr_min, pression_max_pa=20e5):
        """
        Dimensionnement Piston (Axe & Jupe).
        """
        self.inputs = {
            "Diamètre (mm)": 0,
            "Pression Axe (MPa)": 0,
            "Vitesse Moyenne (m/s)": 0
        }

        # 1. GEOMETRIE BASE
        # Jeu thermique Alu/Fonte ou Alu/Acier
        coeff_dilat_alu = 23e-6
        delta_t_skin = 150.0 # Piston chauffe un peu
        jeu_diametral_mm = cyl.alesage_m * 1000.0 * coeff_dilat_alu * delta_t_skin
        
        diametre_mm = cyl.alesage_m * 1000.0 - max(0.10, jeu_diametral_mm)
        
        # 2. AXE DE PISTON
        # D_axe = 25% Bore
        diam_axe_m = cyl.alesage_m * 0.25
        longueur_portee_m = diam_axe_m * 1.5 # Surface portee dans le bossage
        
        # 3. VERIFICATION PRESSION SPECIFIQUE (MATAGE)
        # F = P_max * S_piston
        force_gaz_max_n = pression_max_pa * (math.pi * (cyl.alesage_m/2)**2)
        area_proj_m2 = diam_axe_m * longueur_portee_m
        
        pression_axe_pa = force_gaz_max_n / area_proj_m2
        pression_axe_mpa = pression_axe_pa / 1e6
        
        # 4. RESULTATS
        v_moy_ms = 2 * cyl.course_m * (regime_tr_min / 60.0)
        
        self.inputs["Diamètre (mm)"] = round(diametre_mm, 2)
        self.inputs["Pression Axe (MPa)"] = round(pression_axe_mpa, 1)
        self.inputs["Vitesse Moyenne (m/s)"] = round(v_moy_ms, 2)
        
        limit_bague_bronze = 40.0 # MPa
        alert_msg = ""
        if pression_axe_mpa > limit_bague_bronze:
            alert_msg = f"ATTENTION: Pression Axe {pression_axe_mpa:.1f} > {limit_bague_bronze} MPa. Augmenter diam axe."
        
        self.dimensions = {
            "Diametre_Ext_mm": diametre_mm,
            "Hauteur_Totale_mm": cyl.alesage_m * 0.8 * 1000.0,
            "Diam_Axe_mm": diam_axe_m * 1000.0,
            "Jeu_Montage_mm": jeu_diametral_mm,
            "Nb_Segments": 3
        }
        
        self.materiau = "Alu 7075-T6 (Forgé)"
        self.masse_estimee_kg = 2700 * (math.pi*(cyl.alesage_m/2)**2 * cyl.alesage_m*0.8) * 0.4 # 40% plein
        self.cout_estime_euro = 80.0
