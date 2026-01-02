import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'goupilles_centrage'.
    Assure le positionnement précis des carters/couvercles.
    """

    def __init__(self):
        self.nom = "goupilles_centrage"
        self.diametre_mm = 0.0
        self.longueur_mm = 0.0
        self.quantite = 0

    def dimensionner(self, vis_couvercle, nb_carters: int):
        """
        Dépendances: VisCouvercle (taille relative)
        """
        # Env. 8-10mm ou égal aux vis
        self.diametre_mm = vis_couvercle.diametre_nominal_m * 1000.0
        self.longueur_mm = self.diametre_mm * 2.5
        
        # 2 goupilles par face d'assemblage
        self.quantite = nb_carters * 2 * 2 

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_mm:.1f} mm\n"
                f"  - Quantité: {self.quantite}")
