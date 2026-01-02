import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'huile_graisse'.
    Volume d'huile moteur.
    """

    def __init__(self):
        self.nom = "huile_graisse"
        self.volume_l = 0.0
        self.grade_viscosite = "10W40"
        self.masse_kg = 0.0

    def dimensionner(self, cylindree_totale_m3, has_turbo=True):
        """
        Dimensionne le volume d'huile du carter humide ou sec.
        Empirique: 10 à 20% de la cylindrée ? Non, c'est pour les petits moteurs.
        Pour moteurs industriels: V_huile (L) ~ 0.1 à 0.3 * Puissance (kW) ou formule basée sur cylindrée.
        Formule simple: 4L + 2L par Litre de cylindrée au-delà de 2L.
        """
        cyl_l = cylindree_totale_m3 * 1000.0
        
        # Base 3L
        self.volume_l = 3.0
        if cyl_l > 1.0:
            self.volume_l += (cyl_l - 1.0) * 1.5 # 1.5L par litre supp
            
        if has_turbo:
            self.volume_l += 0.5 # Volume circuit turbo + échangeur
            
        # Masse (Densité 0.85)
        self.masse_kg = self.volume_l * 0.85

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Volume Carter: {self.volume_l:.1f} L (Grade {self.grade_viscosite})\n"
                f"  - Masse Fluide: {self.masse_kg:.1f} kg")
