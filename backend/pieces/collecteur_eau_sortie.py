import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'collecteur_eau_sortie'.
    Collecte l'eau chaude.
    """

    def __init__(self):
        self.nom = "collecteur_eau_sortie"
        self.diametre_interne_mm = 0.0
        self.longueur_m = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, collecteur_entree):
        """
        Dépendances: CollecteurEntree (Symétrique souvent)
        """
        self.diametre_interne_mm = collecteur_entree.diametre_interne_mm
        self.longueur_m = collecteur_entree.longueur_m
        self.masse_kg = collecteur_entree.masse_kg

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_interne_mm:.1f} mm")
