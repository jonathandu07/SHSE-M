import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Pas de module thermique échangeur complet, on structure autour du volume et surface

class Piece:
    """Modèle calculable pour 'echangeur_thermique_corps' (Régénérateur).
    Doit avoir une grande surface d'échange et un volume mort faible.
    """

    def __init__(self):
        self.nom = "echangeur_thermique_corps"
        self.volume_total_m3 = 0.0
        self.porosite = 0.7 # 70% de vide pour le gaz
        self.surface_echange_m2 = 0.0
        self.masse_matrix_kg = 0.0

    def dimensionner(self, cylindre):
        """
        Dépendances: Cylindre
        """
        # Volume relié à la cylindrée (Souvent ~ cylindrée unitaire)
        self.volume_total_m3 = cylindre.cylindree_unitaire_m3
        
        # Surface échange: (Dépend du type de matrice: paille de fer, grilles...)
        # Ratio surface/volume très élevé recherché ~ 2000 m-1
        ratio_sv = 2000.0
        self.surface_echange_m2 = self.volume_total_m3 * ratio_sv
        
        # Masse matrice (Inox ou Cuivre)
        vol_solide = self.volume_total_m3 * (1 - self.porosite)
        densite_inox = 7900.0
        self.masse_matrix_kg = vol_solide * densite_inox

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Volume Total: {self.volume_total_m3*1e6:.0f} cc\n"
                f"  - Surface Echange: {self.surface_echange_m2:.2f} m2\n"
                f"  - Masse Matrice: {self.masse_matrix_kg:.2f} kg")
