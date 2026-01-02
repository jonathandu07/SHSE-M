import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'collecteur_gaz_entree' (Admission/Remplissage)."""

    def __init__(self):
        self.nom = "collecteur_gaz_entree"
        self.diametre_conduit_mm = 0.0
        self.vitesse_gaz_ms = 0.0

    def dimensionner(self, cylindre, regime_tr_min: float):
        """
        Dimensionnement pour vitesse gaz max ~ 80-100 m/s
        Q = V_cyl * N / 2
        """
        debit_m3_s = (cylindre.cylindree_unitaire_m3 * regime_tr_min / 60) / 2 # 4T
        
        # V = Q / A  => A = Q / V_cible
        vitesse_cible = 90.0
        aire = debit_m3_s / vitesse_cible
        
        self.diametre_conduit_mm = 2 * math.sqrt(aire / math.pi) * 1000
        self.vitesse_gaz_ms = vitesse_cible

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre conduit: {self.diametre_conduit_mm:.1f} mm\n"
                f"  - Vitesse Gaz (estim): {self.vitesse_gaz_ms:.0f} m/s")
