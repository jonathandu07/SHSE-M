import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'couvercle_arriere'.
    Ferme le carter à l'arrière (côté volant moteur).
    """

    def __init__(self):
        self.nom = "couvercle_arriere"
        self.diametre_flasque_m = 0.0
        self.epaisseur_m = 0.01 
        self.masse_kg = 0.0
        self.materiau = "Aluminium"

    def dimensionner(self, carter):
        """
        Dépendances: Carter
        """
        # Souvent circulaire ou carré pour tenir le joint spi de vilo
        self.diametre_flasque_m = carter.largeur_m * 0.8
        
        import math
        surface = math.pi * (self.diametre_flasque_m/2)**2
        volume = surface * self.epaisseur_m
        densite = 2700.0
        self.masse_kg = volume * densite

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre Flasque: {self.diametre_flasque_m*1000:.0f} mm\n"
                f"  - Masse: {self.masse_kg:.2f} kg")
