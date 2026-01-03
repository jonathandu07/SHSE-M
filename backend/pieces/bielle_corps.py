import math
import sys
import os

# Ajout du chemin pour importer BasePiece correctement si nécessaire
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from pieces._base_piece import BasePiece

class Piece(BasePiece):
    def __init__(self):
        super().__init__()
        self.name = "Corps de Bielle (Power Rod)"
        self.ref = "MEC-001"
        self.category = "MECANIQUE"
        self.description = "Bielle de transmission de puissance (Piston -> Vilebrequin). Dimensionnée au flambage (Euler)."

    def dimensionner(self, cyl, pis, axe, pression_max_pa, regime_tr_min):
        """
        Dimensionnement RDM avancé (Flambage Euler + Compression Simple).
        Inputs nécessaires :
        - cyl : Objet cylindre (dimensionné)
        - pression_max_pa : Pression max cycle (inc. sécurité)
        """
        self.inputs = {
            "Force Gaz Max (N)": 0,
            "Longueur Entraxe (mm)": 0,
            "Section Calculée (mm2)": 0,
            "Contrainte Compression (MPa)": 0,
            "Facteur Sécurité Flambage": 0
        }

        # 1. PARAMÈTRES GÉOMÉTRIQUES & CHARGE
        # Force max gaz = P_max * Surface Piston
        surface_piston_m2 = math.pi * (cyl.alesage_m / 2)**2
        force_gaz_n = pression_max_pa * surface_piston_m2
        
        # Longueur : Ratio L/C ~ 2.2 (Standard Robuste)
        entraxe_m = cyl.course_m * 2.2
        entraxe_mm = entraxe_m * 1000.0
        
        # 2. DIMENSIONNEMENT SECTION (FLAMBAGE EULER)
        # Critère : F_crit > F_gaz * SF
        SF_FLAMBAGE = 4.0
        MAT_E_MODULUS = 210e9 # Acier 42CrMo4 (Pa)
        RE_MATERIAU_MPA = 900.0 # MPa
        
        # I_req = (F_crit * L^2) / (pi^2 * E)
        f_crit_target = force_gaz_n * SF_FLAMBAGE
        i_req_m4 = (f_crit_target * entraxe_m**2) / (math.pi**2 * MAT_E_MODULUS)
        
        # Hypothèse Section Rectangulaire Pleine (h = 2b) pour simplifier le modèle paramétrique
        # I = b*h^3/12 avec h=2b => I = b*(8b^3)/12 = 2/3 * b^4
        # b = (1.5 * I)^(1/4)
        b_m = (1.5 * i_req_m4)**0.25
        h_m = 2.0 * b_m
        
        epaisseur_mm = b_m * 1000.0
        largeur_mm = h_m * 1000.0
        section_mm2 = epaisseur_mm * largeur_mm
        
        # 3. VÉRIFICATION COMPRESSION SIMPLE
        # sigma = F / S
        contrainte_comp_mpa = (force_gaz_n / (section_mm2 * 1e-6)) / 1e6
        fs_comp = RE_MATERIAU_MPA / contrainte_comp_mpa
        
        # 4. ENREGISTREMENT RÉSULTATS
        self.inputs["Force Gaz Max (N)"] = round(force_gaz_n, 0)
        self.inputs["Longueur Entraxe (mm)"] = round(entraxe_mm, 1)
        self.inputs["Section Calculée (mm2)"] = round(section_mm2, 1)
        self.inputs["Contrainte Compression (MPa)"] = round(contrainte_comp_mpa, 2)
        self.inputs["Facteur Sécurité Flambage"] = SF_FLAMBAGE
        self.inputs["Marge Compression"] = round(fs_comp, 1)

        self.dimensions = {
            "L_entraxe_mm": entraxe_mm,
            "Epaisseur_Corps_mm": epaisseur_mm,
            "Largeur_Corps_mm": largeur_mm,
            "Diam_Pied_mm": axe.diametre_m * 1000.0 + 12.0, # Bossage
            "Diam_Tete_mm": cyl.course_m * 0.6 * 1000.0 + 24.0 # Bossage Maneton
        }
        
        self.masse_estimee_kg = (section_mm2 * 1e-6 * entraxe_m) * 7850 * 1.4 # +40% têtes
        self.materiau = "Acier 42CrMo4 (Trempé Revenu)"
        self.cout_estime_euro = 50.0 + (self.masse_estimee_kg * 18.0)

        # STOCKAGE POUR MODULE SUIVANT
        self.force_compression_max_n = force_gaz_n
