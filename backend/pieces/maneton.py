import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_pertes_frottement import calcul_puissance_frottement_palier

# Note: Pour le maneton, on dimensionne souvent au cisaillement ou à la pression de matage (Hertz/Palier).
# Ici on va calculer la pression moyenne de palier (F/S_proj) et estimer les pertes.

class Piece:
    """Modèle calculable pour 'maneton'."""

    def __init__(self):
        self.nom = "maneton"
        self.diametre_m = 0.0
        self.largeur_m = 0.0
        self.pression_palier_pa = 0.0
        self.puissance_perdue_w = 0.0

    def dimensionner(self, force_max_n: float, diametre_vilebrequin_m: float, vitesse_rotation_tr_min: float):
        # Règle empirique: Diamètre maneton ~ 0.6 * D_vilo_principal
        # (Lui même ~ 0.6 * Alésage, mais restons local)
        self.diametre_m = 0.65 * diametre_vilebrequin_m 
        self.largeur_m = 0.5 * self.diametre_m # Ratio L/D ~ 0.5
        
        aire_projete = self.diametre_m * self.largeur_m
        if aire_projete > 0:
            self.pression_palier_pa = force_max_n / aire_projete
            
        # Estimation Pertes
        # Vitesse glissement v = omega * r
        omega = (3.14159 * 2 * vitesse_rotation_tr_min) / 60
        v_glissement = omega * (self.diametre_m / 2)
        
        # P = f * W * v
        self.puissance_perdue_w = calcul_puissance_frottement_palier(force_max_n, v_glissement, 0.02) # f=0.02 approx

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Largeur: {self.largeur_m*1000:.2f} mm\n"
                f"  - Pression Palier: {self.pression_palier_pa/1e6:.1f} MPa\n"
                f"  - Pertes Frottement (Peak): {self.puissance_perdue_w:.1f} W")
