import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'axe_piston'."""

    def __init__(self):
        self.nom = "axe_piston"
        self.diametre_m = 0.0
        self.longueur_m = 0.0
        self.masse_kg = 0.0
        self.contrainte_cisaillement_max_pa = 0.0
        self.densite_kg_m3 = 7800.0 # Acier

    def dimensionner(self, piston):
        """
        Dépendances: Piston
        """
        # Règle empirique
        self.diametre_m = 0.3 * piston.diametre_m
        self.longueur_m = 0.8 * piston.diametre_m
        
        # Calcul Masse (Tube plein pour simplifier)
        vol_m3 = (3.14159 * self.diametre_m**2 / 4) * self.longueur_m
        self.masse_kg = vol_m3 * self.densite_kg_m3
        
        # Vérif cisaillement
        if self.diametre_m > 0:
            aire_section = 3.14159 * (self.diametre_m**2) / 4
            # Force max vient du piston
            self.contrainte_cisaillement_max_pa = (piston.force_max_gaz_n / 2) / aire_section

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Masse: {self.masse_kg*1000:.0f} g\n"
                f"  - Contrainte Cisaillement: {self.contrainte_cisaillement_max_pa/1e6:.1f} MPa")
