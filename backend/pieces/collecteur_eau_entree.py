import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'collecteur_eau_entree'.
    Distrbue l'eau de refroidissement vers les zones froides.
    """

    def __init__(self):
        self.nom = "collecteur_eau_entree"
        self.diametre_interne_mm = 0.0
        self.longueur_m = 0.0
        self.masse_kg = 0.0
        self.materiau = "Aluminium/Plastique"

    def dimensionner(self, circuit_eau, longueur_bloc_m: float):
        """
        Dépendances: CircuitEau (débit), LongueurBloc (Carter)
        """
        # Vitesse eau cible faible pour pertes charges minimes ~ 1.5 m/s
        vitesse_cible = 1.5
        debit_m3s = circuit_eau.debit_eau_m3h / 3600.0
        
        # S = Q / V
        section_m2 = debit_m3s / vitesse_cible
        self.diametre_interne_mm = math.sqrt(4 * section_m2 / math.pi) * 1000
        
        self.longueur_m = longueur_bloc_m
        
        # Masse (Tube simple épaisseur 2mm)
        epaisseur = 0.002
        vol_matiere = (math.pi * ((self.diametre_interne_mm/1000 + 2*epaisseur)**2 - (self.diametre_interne_mm/1000)**2) / 4) * self.longueur_m
        self.masse_kg = vol_matiere * 2700.0 # Alu

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_interne_mm:.1f} mm\n"
                f"  - Longueur: {self.longueur_m:.2f} m")
