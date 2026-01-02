import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.boite_crabots.calcul_duree_vie_roulement import calcul_charge_equivalente_roulement, calcul_duree_vie_l10, calcul_duree_vie_heures

class Piece:
    """Modèle calculable pour 'roulements_bagues_galet'."""

    def __init__(self):
        self.nom = "roulements_bagues_galet"
        self.type = "bille"
        self.charge_dyn_base_c_n = 50000.0 # Ex: Roulement 6208
        self.duree_vie_heures = 0.0

    def dimensionner(self, force_radiale_n: float, force_axiale_n: float, vitesse_tr_min: float):
        # Hypothèse facteurs X, Y standards
        # Si Fa/Fr < e, X=1, Y=0. Si Fa/Fr > e, X=0.56, Y=...
        # Simplification: X=1, Y=0 (Charge radiale pure dominante ici)
        p_eq = calcul_charge_equivalente_roulement(force_radiale_n, force_axiale_n, 1.0, 0.0)
        
        l10_millions = calcul_duree_vie_l10(self.charge_dyn_base_c_n, p_eq, self.type)
        self.duree_vie_heures = calcul_duree_vie_heures(l10_millions, vitesse_tr_min)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Type: {self.type}\n"
                f"  - Charge Base C: {self.charge_dyn_base_c_n} N\n"
                f"  - Durée vie estimée: {self.duree_vie_heures:.0f} h")
