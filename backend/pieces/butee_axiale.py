import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'butee_axiale'.
    Reprend les efforts axiaux du vilebrequin (si hélicoïdal ou embrayage).
    """

    def __init__(self):
        self.nom = "butee_axiale"
        self.diametre_m = 0.0
        self.epaisseur_m = 0.002
        self.type = "Flasque Bronze/Poly"

    def dimensionner(self, vilebrequin):
        """
        Dépendances: Vilebrequin
        """
        self.diametre_m = vilebrequin.diametre_tourillon_m * 1.5

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.1f} mm\n"
                f"  - Type: {self.type}")
