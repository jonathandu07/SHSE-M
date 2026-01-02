import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'culasse_couvercle_principal'.
    Ferme les cylindres. Soumis à la pression max.
    """

    def __init__(self):
        self.nom = "culasse_couvercle_principal"
        self.longueur_m = 0.0
        self.largeur_m = 0.0
        self.epaisseur_m = 0.0
        self.masse_kg = 0.0
        self.materiau = "Acier/Fonte"

    def dimensionner(self, cylindre, nb_cylindres: int, pression_max_pa: float):
        """
        Dépendances: Cylindre
        """
        # Dimensions planes
        # Recouvre tous les cylindres + marge
        entraxe = cylindre.alesage_m * 1.5
        self.longueur_m = (entraxe * nb_cylindres) + (0.5 * cylindre.alesage_m)
        # Largeur suffisante pour couvrir les têtes
        self.largeur_m = cylindre.alesage_m * 2.5
        
        # Epaisseur pour tenir la pression (Simplification plaque encastrée ou couvercle épais)
        # On utilise une formule dérivée ou sécuritaire basés sur le diamètre du cylindre
        # e = D * sqrt(C * P / Sigma) pour une plaque circulaire
        sigma_adm = 150e6
        constante_plaque = 0.4 # Encastré
        
        self.epaisseur_m = cylindre.alesage_m * math.sqrt(constante_plaque * pression_max_pa / sigma_adm)
        
        # Sécurité min
        if self.epaisseur_m < 0.015:
            self.epaisseur_m = 0.015

        # Masse
        volume = self.longueur_m * self.largeur_m * self.epaisseur_m
        densite = 7800.0
        self.masse_kg = volume * densite

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Dimensions: {self.longueur_m*1000:.0f}x{self.largeur_m*1000:.0f} mm\n"
                f"  - Epaisseur: {self.epaisseur_m*1000:.2f} mm\n"
                f"  - Masse: {self.masse_kg:.1f} kg")
