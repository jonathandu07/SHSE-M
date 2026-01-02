import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'couvercle_avant'.
    Ferme le carter à l'avant (côté distribution/pompes).
    """

    def __init__(self):
        self.nom = "couvercle_avant"
        self.largeur_m = 0.0
        self.hauteur_m = 0.0
        self.epaisseur_m = 0.005 # 5mm standard
        self.masse_kg = 0.0
        self.materiau = "Aluminium"

    def dimensionner(self, carter):
        """
        Dépendances: Carter
        """
        self.largeur_m = carter.largeur_m
        self.hauteur_m = carter.hauteur_m * 0.6 # Couvre le bas moteur principalement
        
        volume = self.largeur_m * self.hauteur_m * self.epaisseur_m
        densite = 2700.0
        self.masse_kg = volume * densite

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Dimensions: {self.largeur_m*1000:.0f}x{self.hauteur_m*1000:.0f} mm\n"
                f"  - Epaisseur: {self.epaisseur_m*1000:.1f} mm\n"
                f"  - Masse: {self.masse_kg:.2f} kg")
