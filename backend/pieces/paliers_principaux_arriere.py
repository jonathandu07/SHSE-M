import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'paliers_principaux_arriere'.
    Côté volant moteur, plus chargé souvent.
    """

    def __init__(self):
        self.nom = "paliers_principaux_arriere"
        self.diametre_interne_m = 0.0
        self.largeur_m = 0.0
        self.type = "Coussinet/Roulement"

    def dimensionner(self, vilebrequin):
        """
        Dépendances: Vilebrequin
        """
        # Souvent identique avant, mais parfois plus large
        self.diametre_interne_m = vilebrequin.diametre_tourillon_m
        self.largeur_m = self.diametre_interne_m * 0.6 

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre Int: {self.diametre_interne_m*1000:.2f} mm\n"
                f"  - Largeur: {self.largeur_m*1000:.1f} mm")
