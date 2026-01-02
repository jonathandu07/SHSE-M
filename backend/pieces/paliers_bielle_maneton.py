import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'paliers_bielle_maneton'.
    Coussinet de tête de bielle (côté vilebrequin).
    """

    def __init__(self):
        self.nom = "paliers_bielle_maneton"
        self.diametre_interne_m = 0.0 # = Diamètre Maneton
        self.largeur_m = 0.0
        self.epaisseur_mm = 0.0
        self.pression_max_pa = 0.0
        self.jeu_radial_m = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, maneton, bielle, pression_huile_pa=4e5, force_max_bielle_n=10000.0):
        """
        Dimensionne le coussinet de tête de bielle.
        """
        # 1. Géométrie
        self.diametre_interne_m = maneton.diametre_m
        
        # Largeur souvent ~0.6 * Diamètre ou imposée par la bielle
        # Ici on s'aligne sur la largeur du maneton (moins un jeu latéral)
        self.largeur_m = maneton.largeur_m - 0.002 # 1mm jeu chaque côté
        if self.largeur_m <= 0: self.largeur_m = maneton.largeur_m * 0.9

        # 2. Charge Specifique
        # P = F / (D * L)
        surface_projete = self.diametre_interne_m * self.largeur_m
        if surface_projete > 0:
            self.pression_max_pa = force_max_bielle_n / surface_projete
        else:
            self.pression_max_pa = 0.0

        # Règle empirique: Pression max < 25-30 MPa pour bronze/alu standard, < 60 MPa pour trimétal
        # On dimensionne l'épaisseur
        if self.diametre_interne_m < 0.05:
            self.epaisseur_mm = 1.5
        elif self.diametre_interne_m < 0.10:
            self.epaisseur_mm = 2.0
        else:
            self.epaisseur_mm = 2.5
            
        # Jeu radial (approx 1/1000 du diamètre)
        self.jeu_radial_m = self.diametre_interne_m * 0.001
        
        # Masse (Approx coquille acier mince)
        # Volume = pi * D * e * L
        vol_m3 = 3.14159 * self.diametre_interne_m * (self.epaisseur_mm/1000) * self.largeur_m
        rho_acier = 7800.0
        self.masse_kg = vol_m3 * rho_acier

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Dimensions: Ø{self.diametre_interne_m*1000:.2f} x L{self.largeur_m*1000:.2f} mm\n"
                f"  - Épaisseur: {self.epaisseur_mm} mm (Jeu {self.jeu_radial_m*1e6:.0f} µm)\n"
                f"  - Pression Max: {self.pression_max_pa/1e6:.1f} MPa\n"
                f"  - Masse: {self.masse_kg*1000:.1f} g")
