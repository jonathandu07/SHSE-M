import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'paroi_mobile_cloison_translateuse'.
    Cloison séparant les volumes ou guidant la tige de déplaceur.
    """

    def __init__(self):
        self.nom = "paroi_mobile_cloison_translateuse"
        self.diametre_externe_m = 0.0
        self.epaisseur_m = 0.015
        self.masse_kg = 0.0

    def dimensionner(self, cylindre):
        """
        Dépendances: Cylindre
        """
        self.diametre_externe_m = cylindre.alesage_m
        
        import math
        surface = math.pi * (self.diametre_externe_m/2)**2
        volume = surface * self.epaisseur_m
        self.masse_kg = volume * 2700.0 # Alu

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_externe_m*1000:.0f} mm\n"
                f"  - Masse: {self.masse_kg:.2f} kg")
