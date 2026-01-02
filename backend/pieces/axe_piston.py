import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Pas de module spécique Axe Piston créé, on utilise des Py-Formules directes ou on en crée un.
# Pour l'instant, règle empirique basée sur la force

class Piece:
    """Modèle calculable pour 'axe_piston'."""

    def __init__(self):
        self.nom = "axe_piston"
        self.diametre_m = 0.0
        self.longueur_m = 0.0
        self.contrainte_cisaillement_max_pa = 0.0

    def dimensionner(self, force_max_n: float, diametre_piston_m: float):
        # Règle empirique : d_axe approx 0.25 à 0.35 * Alésage
        self.diametre_m = 0.3 * diametre_piston_m
        
        # Longueur approx 0.8 * Alésage
        self.longueur_m = 0.8 * diametre_piston_m
        
        # Vérif cisaillement (Double cisaillement)
        # Tau = F / (2 * A) = F / (2 * pi * d^2 / 4) = 2F / (pi * d^2)
        if self.diametre_m > 0:
            aire_section = 3.14159 * (self.diametre_m**2) / 4
            self.contrainte_cisaillement_max_pa = (force_max_n / 2) / aire_section

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Longueur: {self.longueur_m*1000:.2f} mm\n"
                f"  - Contrainte Cisaillement: {self.contrainte_cisaillement_max_pa/1e6:.1f} MPa")
