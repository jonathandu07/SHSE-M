import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'axes_galet'.
    Axe supportant le galet suiveur (côté déplaceur ou piston).
    """

    def __init__(self):
        self.nom = "axes_galet"
        self.diametre_m = 0.0
        self.longueur_m = 0.0
        self.masse_kg = 0.0
        self.materiau = "Acier Trempé"

    def dimensionner(self, force_laterale_max_n: float):
        """
        Dépendances: Force Latérale (issue bielle/rail)
        """
        # Dimensionnement au cisaillement double + flexion
        # Simplifié cisaillement: Tau = F / (2*S) <= Rpg
        rpg = 300e6 # 300 MPa
        section_min = force_laterale_max_n / (2 * rpg)
        self.diametre_m = math.sqrt(4 * section_min / math.pi)
        
        if self.diametre_m < 0.01: self.diametre_m = 0.01 # Min 10mm
        
        self.longueur_m = self.diametre_m * 4.0 # Ratio L/D
        
        volume = math.pi * (self.diametre_m/2)**2 * self.longueur_m
        self.masse_kg = volume * 7800.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Masse: {self.masse_kg*1000:.0f} g")
