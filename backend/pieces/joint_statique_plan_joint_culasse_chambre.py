import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'joint_statique_plan_joint_culasse_chambre'.
    Joint de culasse multi-feuilles ou métallique.
    """

    def __init__(self):
        self.nom = "joint_statique_plan_joint_culasse_chambre"
        self.diametre_nominal_m = 0.0
        self.type_joint = "MLS (Multi-Layer Steel)"

    def dimensionner(self, cylindre):
        """
        Dépendances: Cylindre
        """
        # Doit entourer l'alésage
        self.diametre_nominal_m = cylindre.alesage_m * 1.1

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre nominal: {self.diametre_nominal_m*1000:.1f} mm\n"
                f"  - Type: {self.type_joint}")
