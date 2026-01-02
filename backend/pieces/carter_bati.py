import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'carter_bati'.
    Structure principale.
    """

    def __init__(self):
        self.nom = "carter_bati"
        self.longueur_m = 0.0
        self.largeur_m = 0.0
        self.hauteur_m = 0.0
        self.masse_estimee_kg = 0.0

    def dimensionner(self, cylindre, nb_cylindres: int):
        """
        Dépendances: Cylindre
        """
        # Encombrement ~ (Nb_cyl * Entraxe) x (Largeur vilo) x (Hauteur Cylindre + Vilo)
        entraxe_cyl = cylindre.alesage_m * 1.5
        
        self.longueur_m = entraxe_cyl * nb_cylindres + 0.1 # Marges
        self.largeur_m = cylindre.alesage_m * 3.0 # Largeur bas moteur
        self.hauteur_m = cylindre.hauteur_totale_m * 1.5 
        
        # Volume enveloppe
        vol_env = self.longueur_m * self.largeur_m * self.hauteur_m
        # Taux de remplissage matière ~ 10-15% (beaucoup de vide)
        vol_matiere = vol_env * 0.12
        densite_alu = 2700.0
        
        self.masse_estimee_kg = vol_matiere * densite_alu

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Dimensions: {self.longueur_m*1000:.0f}x{self.largeur_m*1000:.0f}x{self.hauteur_m*1000:.0f} mm\n"
                f"  - Masse estimée: {self.masse_estimee_kg:.1f} kg")
