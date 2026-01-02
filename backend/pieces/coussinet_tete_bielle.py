import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_pertes_frottement import calcul_puissance_frottement_palier

class Piece:
    """Modèle calculable pour 'coussinet_tete_bielle'."""

    def __init__(self):
        self.nom = "coussinet_tete_bielle"
        self.diametre_m = 0.0 # = Diamètre Maneton
        self.largeur_m = 0.0
        self.pression_max_pa = 0.0
        self.puissance_perdue_w = 0.0
        self.epaisseur_m = 0.0015 # Standard ~1.5 - 2mm

    def dimensionner(self, maneton, regime_tr_min: float):
        """
        Dépendances: Maneton
        """
        self.diametre_m = maneton.diametre_m
        self.largeur_m = maneton.largeur_m
        
        # La pression max est celle calculée par le maneton (Charge / Aire)
        self.pression_max_pa = maneton.pression_palier_pa
        
        # Calcul des pertes spécifique au coussinet (Hydrodynamique)
        # P = f * W * v
        # Pour un palier hydrodynamique bien établi, f ~ 0.001 à 0.01
        # On recalcul la charge W à partir de la pression (inversion)
        charge_w = self.pression_max_pa * (self.diametre_m * self.largeur_m)
        
        omega = (3.14159 * 2 * regime_tr_min) / 60
        v_glissement = omega * (self.diametre_m / 2)

        self.puissance_perdue_w = calcul_puissance_frottement_palier(charge_w, v_glissement, 0.005)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Pression Max: {self.pression_max_pa/1e6:.1f} MPa\n"
                f"  - Dissipation thermique: {self.puissance_perdue_w:.1f} W")
