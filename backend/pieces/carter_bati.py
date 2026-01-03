import math
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pieces._base_piece import BasePiece

class Piece(BasePiece):
    def __init__(self):
        super().__init__()
        self.name = "Carter Bâti (Crankcase)"
        self.ref = "CAR-001"
        self.category = "STRUCTURE"
        self.description = "Carter principal sous pression (Buffer space). Dimensionné au Hoop Stress."

    def dimensionner(self, cyl, n_cyl):
        """
        Dimensionnement Pression Interne.
        """
        self.inputs = {
            "Pression Design (bar)": 0,
            "Diametre Interne (mm)": 0,
            "Epaisseur Paroi (mm)": 0,
            "Contrainte Hoop (MPa)": 0
        }

        # 1. PRESSION DESIGN
        # P_buffer approx P_mean
        p_design_bar = 30.0 # Sécurité
        p_design_mpa = p_design_bar / 10.0
        
        # 2. DIAMETRE INTERNE
        # Doit contenir le vilbrequin et les bielles
        # D_int > Course + Encombrement Tetes
        # Approx: D_int = Course * 1.8
        d_int_mm = cyl.course_m * 1000.0 * 1.8
        
        # 3. EPAISSEUR PAROIS (FONTE)
        SIGMA_ALLOW = 250.0 / 4.0 # SF = 4 pour Fonte
        
        # t = P * D / (2 * Sigma)
        t_calc_mm = (p_design_mpa * d_int_mm) / (2 * SIGMA_ALLOW)
        t_final_mm = max(6.0, t_calc_mm) # Minimum fonderie
        
        # Recalcul Stress
        sigma_hoop = (p_design_mpa * d_int_mm) / (2 * t_final_mm)
        
        # 4. RESULTATS
        self.inputs["Pression Design (bar)"] = p_design_bar
        self.inputs["Diametre Interne (mm)"] = round(d_int_mm, 1)
        self.inputs["Epaisseur Paroi (mm)"] = round(t_final_mm, 1)
        self.inputs["Contrainte Hoop (MPa)"] = round(sigma_hoop, 1)
        
        longueur_totale_mm = d_int_mm * n_cyl + 100.0
        
        self.dimensions = {
            "Longueur_mm": longueur_totale_mm,
            "Largeur_mm": d_int_mm + 2*t_final_mm + 40.0, # Brides
            "Hauteur_mm": d_int_mm * 1.5,
            "Epaisseur_Min_mm": t_final_mm
        }
        
        self.materiau = "Fonte Grise GL (Moulée)"
        self.masse_estimee_kg = longueur_totale_mm/1000 * (d_int_mm/1000)**2 * 7200 * 0.5 # Forme creuse
        self.cout_estime_euro = 1500.0
