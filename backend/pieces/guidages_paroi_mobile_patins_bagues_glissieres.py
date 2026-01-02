import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle générique pour 'guidages_paroi_mobile_patins_bagues_glissieres'."""

    def __init__(self):
        self.nom = "guidages_paroi_mobile_patins_bagues_glissieres"

    def dimensionner(self, *args, **kwargs):
        """Dimensionnement par défaut (Pass-through)."""
        pass

    def decrire(self) -> str:
        return f"Pièce: {self.nom} (Standard)"
