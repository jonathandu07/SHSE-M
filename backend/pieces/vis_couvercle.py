import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_precharge_vis import calcul_force_separation, calcul_precharge_vis_totale, calcul_couple_serrage

class Piece:
    """Modèle calculable pour 'vis_couvercle'."""

    def __init__(self):
        self.nom = "vis_couvercle"
        self.nombre_vis = 4
        self.diametre_nominal_m = 0.006 # M6 par défaut
        self.force_precharge_par_vis_n = 0.0
        self.couple_serrage_nm = 0.0

    def dimensionner(self, pression_max_pa: float, diametre_couvercle_m: float):
        aire_eff = math.pi * (diametre_couvercle_m**2) / 4
        
        # 1. Force qui pousse le couvercle
        f_sep = calcul_force_separation(pression_max_pa, aire_eff)
        
        # 2. Précharge totale requise (Coef sécu 1.5, Joint ignoré pour simplif)
        f_tot = calcul_precharge_vis_totale(f_sep, 0, 1.5)
        
        # Choix nb vis (Empirique: Périmètre / Espacement)
        perimetre = math.pi * diametre_couvercle_m
        espacement_cible = 0.05 # 5 cm
        self.nombre_vis = max(4, int(perimetre / espacement_cible))
        
        self.force_precharge_par_vis_n = f_tot / self.nombre_vis
        
        # Choix diamètre (Si Sigma_adm = 600 MPa (Classe 8.8))
        sigma_adm = 600e6 
        section_requise = self.force_precharge_par_vis_n / sigma_adm
        diametre_requis = 2 * math.sqrt(section_requise / math.pi)
        
        # Standardisation très basique (M6, M8, M10)
        if diametre_requis < 0.006: self.diametre_nominal_m = 0.006
        elif diametre_requis < 0.008: self.diametre_nominal_m = 0.008
        elif diametre_requis < 0.010: self.diametre_nominal_m = 0.010
        else: self.diametre_nominal_m = 0.012

        # 3. Couple serrage
        self.couple_serrage_nm = calcul_couple_serrage(self.force_precharge_par_vis_n, self.diametre_nominal_m)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Nombre: {self.nombre_vis}\n"
                f"  - Diamètre: M{self.diametre_nominal_m*1000:.0f}\n"
                f"  - Précharge/vis: {self.force_precharge_par_vis_n:.0f} N\n"
                f"  - Couple Serrage: {self.couple_serrage_nm:.1f} N.m")
