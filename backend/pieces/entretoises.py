import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'entretoises'.
    Pièces d'écartement tubulaires.
    """

    def __init__(self):
        self.nom = "entretoises"
        self.diametre_interne_m = 0.0
        self.diametre_externe_m = 0.0
        self.longueur_m = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, diametre_vis_m, longueur_requise_m):
        """
        Dimensionne une entretoise pour une vis donnée.
        """
        self.diametre_interne_m = diametre_vis_m + 0.001 # Jeu passage
        # Épaisseur paroi standard ~ 20% diamètre
        self.diametre_externe_m = self.diametre_interne_m * 1.5
        self.longueur_m = longueur_requise_m
        
        # Masse (Acier)
        surface = (3.14159 / 4) * (self.diametre_externe_m**2 - self.diametre_interne_m**2)
        vol = surface * self.longueur_m
        self.masse_kg = vol * 7850.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Dim: Ø{self.diametre_interne_m*1000:.1f}/Ø{self.diametre_externe_m*1000:.1f} x L{self.longueur_m*1000:.1f} mm\n"
                f"  - Masse: {self.masse_kg*1000:.1f} g")
