import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'clavettes_cannelures'.
    Liaison Arbre/Volant.
    """

    def __init__(self):
        self.nom = "clavettes_cannelures"
        self.type = "Clavette Parallèle"
        self.largeur_mm = 0.0
        self.hauteur_mm = 0.0
        self.longueur_mm = 0.0

    def dimensionner(self, arbre_sortie):
        """
        Dépendances: ArbreSortie
        """
        # Dimensions standard ISO selon diamètre arbre
        d = arbre_sortie.diametre_m * 1000.0
        if d < 22:
            self.largeur_mm = 6
            self.hauteur_mm = 6
        elif d < 30:
            self.largeur_mm = 8
            self.hauteur_mm = 7
        elif d < 40:
            self.largeur_mm = 10
            self.hauteur_mm = 8
        else:
            self.largeur_mm = 12
            self.hauteur_mm = 8
            
        self.longueur_mm = d * 1.5

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Type: {self.type} {self.largeur_mm}x{self.hauteur_mm}x{self.longueur_mm}")
