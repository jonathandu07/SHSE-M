import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_vitesse_piston import calcul_vitesse_moyenne_piston
from backend.modules.moteur_thermique.calcul_force_gaz import calcul_force_gaz

class Piece:
    """Modèle calculable pour 'piston_puissance'."""

    def __init__(self):
        self.nom = "piston_puissance"
        self.diametre_m = 0.0
        self.hauteur_compression_m = 0.0
        self.vitesse_moyenne_ms = 0.0
        self.force_max_gaz_n = 0.0
        self.masse_kg = 0.0 # Nouvelle propriété critique pour la bielle
        self.matiere = "Alu"
        self.densite_kg_m3 = 2700.0 # Alu

    def dimensionner(self, cylindre, regime_tr_min: float, pression_max_pa: float):
        """
        Dépendances: Cylindre
        """
        self.diametre_m = cylindre.alesage_m
        
        # 1. Vitesse moyenne
        self.vitesse_moyenne_ms = calcul_vitesse_moyenne_piston(cylindre.course_m, regime_tr_min)
        
        # 2. Force Max gaz
        self.force_max_gaz_n = calcul_force_gaz(pression_max_pa, self.diametre_m)

        # 3. Géométrie et Masse estimée
        self.hauteur_compression_m = 0.5 * self.diametre_m
        # Volume estimé ~ Surface * 0.8 * Diamètre (jupe incluse)
        volume_estim_m3 = (math.pi * (self.diametre_m**2) / 4) * (0.8 * self.diametre_m)
        self.masse_kg = volume_estim_m3 * self.densite_kg_m3

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Masse estimée: {self.masse_kg*1000:.0f} g\n"
                f"  - Force Max Gaz: {self.force_max_gaz_n/1000:.2f} kN")
