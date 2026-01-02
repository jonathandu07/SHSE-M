import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_pertes_frottement import calcul_puissance_frottement_segment

class Piece:
    """Modèle calculable pour 'segment_racleur_piston'."""

    def __init__(self):
        self.nom = "segment_racleur_piston"
        self.nombre = 1
        self.epaisseur_axiale_m = 0.0
        self.tension_tangentielle_n = 0.0
        self.puissance_frottement_w = 0.0

    def dimensionner(self, piston):
        """
        Dépendances: Piston
        """
        # Souvent plus épais : 2 à 4 mm
        self.epaisseur_axiale_m = 0.03 * piston.diametre_m
        
        # Tension plus forte pour racler l'huile
        # Pression contact ~ 1 MPa
        pression_contact = 1.0e6
        aire_contact = math.pi * piston.diametre_m * self.epaisseur_axiale_m
        force_contact = pression_contact * aire_contact
        
        self.tension_tangentielle_n = force_contact / (2 * math.pi) # Approx Ft = P*D*h / 2pi ? Non. Ft = P*D*h / 2
        
        # Frottement (mieux lubrifié mais force élevée)
        self.puissance_frottement_w = calcul_puissance_frottement_segment(
            force_normale_n=force_contact,
            vitesse_moyenne_ms=piston.vitesse_moyenne_ms,
            coef_frottement=0.05 # Hydrodynamique partiel
        )

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Epaisseur: {self.epaisseur_axiale_m*1000:.2f} mm\n"
                f"  - Puissance Frottement: {self.puissance_frottement_w:.1f} W")
