import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'ecrous'.
    Écrous hexagonaux standard H.
    """

    def __init__(self):
        self.nom = "ecrous"
        self.diametre_nominal_m = 0.0
        self.hauteur_mm = 0.0
        self.surplat_mm = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, diametre_vis_m, classe_qualite=10.9):
        """
        Dimensionne l'écrou standard (ISO 4032).
        """
        self.diametre_nominal_m = diametre_vis_m
        d_mm = diametre_vis_m * 1000.0
        
        # Approx ISO 4032
        self.hauteur_mm = d_mm * 0.8
        self.surplat_mm = d_mm * 1.6 # Approx s ~ 1.6d
        
        # Masse (Approx Vol Cylindre Hexa - Trou)
        # Vol Hex ~ 0.866 * s^2 * h
        aire_hex = 0.866 * (self.surplat_mm/1000.0)**2
        aire_trou = (3.14159 / 4) * self.diametre_nominal_m**2
        vol = (aire_hex - aire_trou) * (self.hauteur_mm/1000.0)
        self.masse_kg = vol * 7850.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - M{self.diametre_nominal_m*1000:.0f} (H={self.hauteur_mm:.1f}mm, S={self.surplat_mm:.1f}mm)\n"
                f"  - Masse Unitaire: {self.masse_kg*1000:.1f} g")
