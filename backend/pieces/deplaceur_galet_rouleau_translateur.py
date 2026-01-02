import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'deplaceur_galet_rouleau_translateur'.
    Élément mobile qui déplace le gaz chaud/froid.
    """

    def __init__(self):
        self.nom = "deplaceur_galet_rouleau_translateur"
        self.diametre_m = 0.0
        self.longueur_m = 0.0
        self.course_m = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, chambre_chaude, cylindre):
        """
        Dépendances: ChambreChaude, Cylindre
        """
        # Doit entrer dans la chambre chaude (avec jeu)
        self.diametre_m = chambre_chaude.diametre_interne_m * 0.98 # 2% jeu radial
        
        # Course souvent identique ou liée à la course piston
        self.course_m = cylindre.course_m
        
        # Longueur : Doit isoler thermiquement, souvent long (1.5x D)
        self.longueur_m = self.diametre_m * 1.5
        
        # Masse légère (paroi mince vide)
        epaisseur_tole = 0.002 # 2mm
        surface = math.pi * self.diametre_m * self.longueur_m + 2 * (math.pi * self.diametre_m**2 / 4)
        vol_matiere = surface * epaisseur_tole
        self.masse_kg = vol_matiere * 7800 # Acier

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.1f} mm\n"
                f"  - Longueur: {self.longueur_m*1000:.1f} mm\n"
                f"  - Masse: {self.masse_kg*1000:.0f} g")
