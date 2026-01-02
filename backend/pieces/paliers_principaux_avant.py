import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'paliers_principaux_avant'.
    Roulement ou Coussinet supportant le vilebrequin à l'avant.
    """

    def __init__(self):
        self.nom = "paliers_principaux_avant"
        self.diametre_interne_m = 0.0
        self.largeur_m = 0.0
        self.type = "Coussinet"

    def dimensionner(self, vilebrequin):
        """
        Dépendances: Vilebrequin
        """
        self.diametre_interne_m = vilebrequin.diametre_tourillon_m
        self.largeur_m = self.diametre_interne_m * 0.5 # Ratio standard 0.5

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre Int: {self.diametre_interne_m*1000:.2f} mm\n"
                f"  - Largeur: {self.largeur_m*1000:.1f} mm")
