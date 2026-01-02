import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle générique pour 'contrepoids_equilibrage'."""

    def __init__(self):
        self.nom = "contrepoids_equilibrage"

    def dimensionner(self, *args, **kwargs):
        """Dimensionnement par défaut (Pass-through)."""
        pass

    def decrire(self) -> str:
        return f"Pièce: {self.nom} (Standard)"
