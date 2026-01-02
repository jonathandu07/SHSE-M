import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'coussinet_pied_bielle'."""

    def __init__(self):
        self.nom = "coussinet_pied_bielle" # Souvent bague bronze
        self.diametre_m = 0.0 # = Axe Piston
        self.largeur_m = 0.0 # Largeur pied bielle
        self.pression_max_pa = 0.0

    def dimensionner(self, axe_piston, bielle):
        """
        Dépendances: AxePiston, Bielle
        """
        self.diametre_m = axe_piston.diametre_m
        
        # Largeur Pied souvent un peu moins que la longueur axe ou largeur piston
        # Disons 0.5 * Longueur Axe (l'axe dépasse ou est tenu par le piston sur les côtés)
        self.largeur_m = axe_piston.longueur_m * 0.6
        
        # Pression de contact (Mouvement oscillant)
        # Force max = Force gaz transmise par piston -> Axe -> Bielle
        # On récupère F_comp de la bielle
        force_transmission = bielle.force_compression_max_n
        
        aire_projete = self.diametre_m * self.largeur_m
        if aire_projete > 0:
            self.pression_max_pa = force_transmission / aire_projete

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Pression Contact: {self.pression_max_pa/1e6:.1f} MPa")
