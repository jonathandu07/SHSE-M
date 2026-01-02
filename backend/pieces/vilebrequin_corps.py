import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_couple_vilebrequin import calcul_couple_instantane

class Piece:
    """Modèle calculable pour 'vilebrequin_corps'."""

    def __init__(self):
        self.nom = "vilebrequin_corps"
        self.rayon_manivelle_m = 0.0
        self.diametre_tourillon_m = 0.0
        self.couple_max_approx_nm = 0.0

    def dimensionner(self, cylindre, bielle, nb_cylindres=4):
        """
        Dépendances: Cylindre, Bielle
        """
        self.rayon_manivelle_m = cylindre.course_m / 2
        
        # Simplification: 1 maneton par cylindre (Moteur Ligne)
        self.nb_manetons = nb_cylindres
        
        # Dimensionnement Tourillon (Empirique ~ 0.7 * Alésage ou basé sur torsion)
        self.diametre_tourillon_m = 0.7 * cylindre.alesage_m

        # Estimation couple max (Approximation T = F_bielle * r)
        # On ignore ici que le pic de pression n'est pas à 90°, c'est une enveloppe de sécurité
        self.couple_max_approx_nm = calcul_couple_instantane(bielle.force_compression_max_n, self.rayon_manivelle_m, 90)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Rayon Manivelle: {self.rayon_manivelle_m*1000:.2f} mm\n"
                f"  - Diam. Tourillon: {self.diametre_tourillon_m*1000:.2f} mm\n"
                f"  - Couple Max Enveloppe: {self.couple_max_approx_nm:.1f} N.m")
