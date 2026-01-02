import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_vitesse_piston import calcul_vitesse_moyenne_piston
from backend.modules.moteur_thermique.calcul_force_gaz import calcul_force_gaz

class Piece:
    """Modèle calculable pour 'piston_puissance'."""

    def __init__(self):
        self.nom = "piston_puissance"
        self.diametre_m = 0.0
        self.hauteur_compression_m = 0.0 # Axe -> Calotte
        self.vitesse_moyenne_ms = 0.0
        self.force_max_gaz_n = 0.0
        self.matiere = "Alu"

    def dimensionner(self, alesage_m: float, course_m: float, regime_tr_min: float, pression_max_pa: float):
        self.diametre_m = alesage_m
        
        # 1. Vitesse moyenne (Critère fiabilité)
        self.vitesse_moyenne_ms = calcul_vitesse_moyenne_piston(course_m, regime_tr_min)
        
        # 2. Force Max gaz (Dimensionnement axe/bielle)
        self.force_max_gaz_n = calcul_force_gaz(pression_max_pa, alesage_m)

        # 3. Hauteur compression (Règle empirique ~ 0.4 - 0.6 * B)
        self.hauteur_compression_m = 0.5 * alesage_m

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Vitesse moy piston: {self.vitesse_moyenne_ms:.2f} m/s\n"
                f"  - Force Max Gaz: {self.force_max_gaz_n/1000:.2f} kN")
