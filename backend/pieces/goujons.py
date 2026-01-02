import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'goujons'.
    Tirants d'assemblage culasse/carter.
    """

    def __init__(self):
        self.nom = "goujons"
        self.diametre_m = 0.0
        self.longueur_m = 0.0
        self.nombre_total = 0
        self.force_tension_max_n = 0.0

    def dimensionner(self, vis_couvercle, nb_cylindres: int, carter_bati):
        """
        Dépendances: VisCouvercle (pour diam), Carter (pour longueur)
        Note: Les vis de culasse sont souvent des goujons.
        """
        self.diametre_m = vis_couvercle.diametre_nominal_m
        self.force_tension_max_n = vis_couvercle.force_precharge_par_vis_n
        
        # 4 par cylindre min + quelques uns
        self.nombre_total = vis_couvercle.nombre_vis * nb_cylindres
        
        # Longueur traversante hauteur carter partie haute
        self.longueur_m = carter_bati.hauteur_m * 0.6 

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Nombre: {self.nombre_total}\n"
                f"  - Diamètre: M{self.diametre_m*1000:.0f}\n"
                f"  - Tension: {self.force_tension_max_n:.0f} N")
