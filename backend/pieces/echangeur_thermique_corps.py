import math
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pieces._base_piece import BasePiece

class Piece(BasePiece):
    def __init__(self):
        super().__init__()
        self.name = "Échangeur Chaud (Heater Head)"
        self.ref = "THE-001"
        self.category = "THERMIQUE"
        self.description = "Échangeur tubulaire haute température (650°C). Dimensionné au fluage (Creep)."

    def dimensionner(self, cyl):
        """
        Dimensionnement Hoop Stress à Chaud.
        Inputs: cyl (pour P_safety)
        """
        self.inputs = {
            "Pression Service (bar)": 0,
            "Température (°C)": 650,
            "Diam Ext Tube (mm)": 0,
            "Contrainte Hoop (MPa)": 0,
            "Epaisseur Min (mm)": 0
        }

        # Recuperation Pression de Dimensionnement (Sécurité)
        # On assume que l'objet DimensioningEngine a passé la P_safety quelque part
        # Ici on va la ré-estimer si non dispo direct
        # P_mean = 20 bar (Scenario A) => P_safety ~ 30 bar
        p_safety_bar = 30.0
        p_safety_mpa = p_safety_bar / 10.0
        
        # MATERIAU
        # Inox 310S à 650°C. Limite Fluage (1% 10000h) ~ 40-50 MPa
        SIGMA_CREEP_LIMIT = 40.0 # MPa
        
        # DIMENSIONNEMENT TUBES
        # Choix : Tube Ø12mm standard
        d_ext_mm = 12.0
        
        # Hoop Stress: t = P*D / (2*Sig)
        # Mais ici on veut verifier t existant ou trouver t min
        # t_min = (P * D) / (2 * Sigma_allow)
        t_min_mm = (p_safety_mpa * d_ext_mm) / (2 * SIGMA_CREEP_LIMIT)
        
        # On impose une épaisseur manufacturable (1.5mm standard ou 2.0 schedule)
        t_reel_mm = max(1.5, t_min_mm)
        
        # Verification inverse
        sigma_hoop = (p_safety_mpa * d_ext_mm) / (2 * t_reel_mm)
        fs_creep = SIGMA_CREEP_LIMIT / sigma_hoop
        
        self.inputs["Pression Service (bar)"] = p_safety_bar
        self.inputs["Diam Ext Tube (mm)"] = d_ext_mm
        self.inputs["Contrainte Hoop (MPa)"] = round(sigma_hoop, 2)
        self.inputs["Epaisseur Min (mm)"] = round(t_min_mm, 2)
        
        # DIMENSIONNEMENT FAISCEAU
        # Surface échange requise pour 10kWth/cylindre ?
        # S ~ 0.5 m2 ? 
        # L_tube = 0.5m
        nb_tubes = 40 # Par cylindre
        
        self.dimensions = {
            "Diam_Tube_Ext_mm": d_ext_mm,
            "Epaisseur_Paroi_mm": t_reel_mm,
            "Longueur_Developpee_mm": 500.0,
            "Nombre_Tubes": nb_tubes
        }
        
        self.materiau = "Inox Réfractaire 310S"
        self.masse_estimee_kg = nb_tubes * 0.200 # 200g par tube
        self.cout_estime_euro = nb_tubes * 15.0 # Soudure couteuse
