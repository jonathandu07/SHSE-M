import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'rail_glissiere_translation_galet'.
    Guide la translation pour absorber les efforts latéraux.
    """

    def __init__(self):
        self.nom = "rail_glissiere_translation_galet"
        self.longueur_m = 0.0
        self.largeur_piste_m = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, cylindre, axe_galet):
        """
        Dépendances: Cylindre (Course), AxeGalet (Largeur contact)
        """
        # Longueur course + encombrement galet + marge
        self.longueur_m = cylindre.course_m + (2 * axe_galet.diametre_m)
        
        # Largeur piste > Diamètre axe (si galet plus gros) ou via galet
        # On estime largeur piste ~ 2 * Diamètre Axe
        self.largeur_piste_m = axe_galet.diametre_m * 2.0
        
        # Masse (Barreau acier usiné)
        epaisseur = 0.01
        volume = self.longueur_m * (self.largeur_piste_m + 0.02) * epaisseur
        self.masse_kg = volume * 7800.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Longueur: {self.longueur_m*1000:.0f} mm\n"
                f"  - Largeur Piste: {self.largeur_piste_m*1000:.1f} mm")
