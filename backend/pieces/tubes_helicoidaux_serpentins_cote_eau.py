import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import calcul_epaisseur_cylindre_mince

class Piece:
    """Modèle calculable pour 'tubes_helicoidaux_serpentins_cote_eau'.
    Tubes de refroidissement.
    """

    def __init__(self):
        self.nom = "tubes_helicoidaux_serpentins_cote_eau"
        self.nombre_tubes = 10
        self.diametre_interne_m = 0.005 # 5mm
        self.longueur_tube_m = 1.0 
        self.epaisseur_paroi_m = 0.0
        self.surface_echange_totale_m2 = 0.0

    def dimensionner(self, chambre_froide, pression_max_pa: float):
        """
        Dépendances: ChambreFroide
        """
        # Similaire chambre chaude mais sur chambre froide
        # Si chambre froide non-tubulaire (ex: chemise eau), alors ces tubes sont peut-être l'échangeur externe.
        # On assume enroulement autour.
        
        # Check if chambre_froide has dimensions (it should)
        dia = 0.1 # Default
        if hasattr(chambre_froide, 'diametre_interne_m'): 
             dia = chambre_froide.diametre_interne_m
        
        perimetre = math.pi * dia
        nb_tours = 10 
        self.longueur_tube_m = nb_tours * perimetre
        
        self.surface_echange_totale_m2 = self.nombre_tubes * (math.pi * self.diametre_interne_m * self.longueur_tube_m)
        
        # Pression interne de l'eau pas énorme (quelques bars), mais si c'est l'échangeur gaz-eau, la paroi voit la P_gaz.
        # "cote_eau" -> contient l'eau. Si immergé dans gaz, subit P_gaz externe.
        # Si contient le gaz (non, c'est cote_eau), donc contient eau. Pression eau ~ 3 bars.
        # MAIS si c'est un serpentin dans le carter pressurisée ?
        # Assumons P_eau ~ 5 bars. P_gaz externe ?
        # Dimensionnons pour P_diff = 5 bars (supporte sa propre pression).
        
        sigma_adm = 150e6 # Cuivre/Inox froid
        self.epaisseur_paroi_m = calcul_epaisseur_cylindre_mince(5e5, self.diametre_interne_m/2, sigma_adm)
        if self.epaisseur_paroi_m < 0.0005: self.epaisseur_paroi_m = 0.0005 # 0.5mm min

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Nb Tubes: {self.nombre_tubes}\n"
                f"  - Surface Echange: {self.surface_echange_totale_m2:.2f} m2")
