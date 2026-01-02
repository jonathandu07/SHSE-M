import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'joints_statiques_collecteurs_gaz'.
    Joints haute température (Cuivre, Graphite armé) pour collecteurs gaz.
    """

    def __init__(self):
        self.nom = "joints_statiques_collecteurs_gaz"
        self.diametre_m = 0.0
        self.quantite = 0
        self.temperature_max_c = 750

    def dimensionner(self, diametre_tube_m: float, nombre_connexions: int):
        """
        Dépendances: Diamètre tubulure gaz
        """
        self.diametre_m = diametre_tube_m * 1.05
        self.quantite = nombre_connexions

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.1f} mm\n"
                f"  - Température Max: {self.temperature_max_c}°C")
