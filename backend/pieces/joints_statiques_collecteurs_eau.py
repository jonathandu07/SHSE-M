import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'joints_statiques_collecteurs_eau'.
    Joints toriques ou plats pour raccordement eau.
    """

    def __init__(self):
        self.nom = "joints_statiques_collecteurs_eau"
        self.diametre_m = 0.0
        self.quantite = 0

    def dimensionner(self, diametre_tube_m: float, nombre_connexions: int):
        """
        Dépendances: Diamètre tubulure
        """
        self.diametre_m = diametre_tube_m
        self.quantite = nombre_connexions * 2 # Entrée/Sortie

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.1f} mm\n"
                f"  - Quantité estimée: {self.quantite}")
