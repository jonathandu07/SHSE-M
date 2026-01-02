import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'collecteur_gaz_sortie' (Echappement/Refoulement)."""

    def __init__(self):
        self.nom = "collecteur_gaz_sortie"
        self.diametre_conduit_mm = 0.0
        self.vitesse_gaz_ms = 0.0

    def dimensionner(self, collecteur_entree):
        """
        Dépendances: CollecteurEntree
        Souvent plus gros si détente, mais en Stirling circuit fermé,
        le 'Refoulement' est souvent vers le refroidisseur.
        On dimensionne similaire à l'admission pour l'instant.
        """
        self.diametre_conduit_mm = collecteur_entree.diametre_conduit_mm
        self.vitesse_gaz_ms = collecteur_entree.vitesse_gaz_ms

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_conduit_mm:.1f} mm")
