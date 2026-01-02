import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'isolation_thermique_externe'.
    Enveloppe isolante parties chaudes.
    """

    def __init__(self):
        self.nom = "isolation_thermique_externe"
        self.epaisseur_m = 0.05
        self.volume_m3 = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, ch_chaude, nb_cylindres: int):
        """
        Dépendances: ChambreChaude
        """
        # Volume enveloppe autour chambre chaude
        # V_iso = Surface * epaisseur
        import math
        surface_ch = math.pi * ch_chaude.diametre_interne_m**2 # approx sphere
        self.volume_m3 = surface_ch * self.epaisseur_m * nb_cylindres
        
        densite_laine = 100.0 # kg/m3
        self.masse_kg = self.volume_m3 * densite_laine

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Epaisseur: {self.epaisseur_m*1000:.0f} mm\n"
                f"  - Masse isolant: {self.masse_kg:.2f} kg")
