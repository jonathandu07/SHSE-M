import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import calcul_epaisseur_cylindre_mince

class Piece:
    """Modèle calculable pour 'tubes_helicoidaux_serpentins_cote_gaz'.
    Tubes chauffants.
    """

    def __init__(self):
        self.nom = "tubes_helicoidaux_serpentins_cote_gaz"
        self.nombre_tubes = 10
        self.diametre_interne_m = 0.005 # 5mm
        self.longueur_tube_m = 1.0 
        self.epaisseur_paroi_m = 0.0
        self.surface_echange_totale_m2 = 0.0

    def dimensionner(self, chambre_chaude, pression_max_pa: float):
        """
        Dépendances: ChambreChaude
        """
        # Doit entourer la chambre chaude ou être dedans
        perimetre_chambre = math.pi * chambre_chaude.diametre_interne_m
        
        # Longueur = N tours * perimetre
        nb_tours = 10 
        self.longueur_tube_m = nb_tours * perimetre_chambre
        
        # Surface échange
        self.surface_echange_totale_m2 = self.nombre_tubes * (math.pi * self.diametre_interne_m * self.longueur_tube_m)
        
        # Epaisseur tenue pression
        # Haute Température -> Sigma adm faible
        sigma_adm = 100e6
        self.epaisseur_paroi_m = calcul_epaisseur_cylindre_mince(pression_max_pa, self.diametre_interne_m/2, sigma_adm)
        if self.epaisseur_paroi_m < 0.001: self.epaisseur_paroi_m = 0.001 # Min fabricable

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Nb Tubes: {self.nombre_tubes}\n"
                f"  - Longueur Totale: {self.longueur_tube_m * self.nombre_tubes:.1f} m\n"
                f"  - Surface Echange: {self.surface_echange_totale_m2:.2f} m2")
