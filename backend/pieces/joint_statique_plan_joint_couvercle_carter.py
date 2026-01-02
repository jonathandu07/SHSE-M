import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'joint_statique_plan_joint_couvercle_carter'.
    Joint papier/pâte pour les couvercles.
    """

    def __init__(self):
        self.nom = "joint_statique_plan_joint_couvercle_carter"
        self.perimetre_total_m = 0.0
        self.type_joint = "Papier/Elastomere"

    def dimensionner(self, carter, couvercle_avant, couvercle_arriere):
        """
        Dépendances: Carter, Couvercles
        """
        # Somme des périmètres
        peri_avant = 2 * (couvercle_avant.largeur_m + couvercle_avant.hauteur_m)
        import math
        peri_arriere = math.pi * couvercle_arriere.diametre_flasque_m
        
        self.perimetre_total_m = peri_avant + peri_arriere

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Périmètre total à étancher: {self.perimetre_total_m:.2f} m\n"
                f"  - Type: {self.type_joint}")
