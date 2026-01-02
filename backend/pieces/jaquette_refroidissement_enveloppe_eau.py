import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'jaquette_refroidissement_enveloppe_eau'.
    Chemise d'eau entourant le cylindre pour le refroidissement.
    """

    def __init__(self):
        self.nom = "jaquette_refroidissement_enveloppe_eau"
        self.diametre_interne_m = 0.0
        self.diametre_externe_m = 0.0
        self.hauteur_m = 0.0
        self.volume_eau_l = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, cylindre, epaisseur_lame_eau_mm=5.0):
        """
        Dimensionne l'enveloppe d'eau autour du cylindre.
        """
        self.diametre_interne_m = cylindre.alesage_m + (2 * cylindre.epaisseur_paroi_m)
        diam_ext_cylindre = self.diametre_interne_m
        
        # Lame d'eau
        self.diametre_externe_m = diam_ext_cylindre + 2 * (epaisseur_lame_eau_mm / 1000.0)
        
        # Hauteur (toute la course + marge)
        self.hauteur_m = cylindre.hauteur_totale_m * 0.8 # On ne refroidit pas tout le bas de jupe
        
        # Volume Eau (Annulaire)
        surface_annulaire = (3.14159 / 4) * (self.diametre_externe_m**2 - self.diametre_interne_m**2)
        vol_m3 = surface_annulaire * self.hauteur_m
        self.volume_eau_l = vol_m3 * 1000.0
        
        # Masse de la jaquette elle-même (Paroi externe fine, ex: 3mm Alu)
        epaisseur_paroi_ext = 0.003
        diam_ext_jaquette = self.diametre_externe_m + 2 * epaisseur_paroi_ext
        surface_ann_jaquette = (3.14159 / 4) * (diam_ext_jaquette**2 - self.diametre_externe_m**2)
        vol_alu_m3 = surface_ann_jaquette * self.hauteur_m
        self.masse_kg = vol_alu_m3 * 2700.0 # Alu

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Lame d'eau: {((self.diametre_externe_m - self.diametre_interne_m)/2)*1000:.1f} mm\n"
                f"  - Volume Eau: {self.volume_eau_l:.2f} L\n"
                f"  - Masse Jaquette: {self.masse_kg:.2f} kg")
