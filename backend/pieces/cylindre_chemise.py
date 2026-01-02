import sys
import os
import math

# Hack pour import dynamique si exécuté directement
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_cylindree import calcul_cylindree_unitaire
from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import calcul_epaisseur_cylindre_mince

class Piece:
    """Modèle calculable pour 'cylindre_chemise'."""

    def __init__(self):
        self.nom = "cylindre_chemise"
        self.alesage_m = 0.0
        self.course_m = 0.0
        self.cylindree_unitaire_m3 = 0.0
        self.epaisseur_paroi_m = 0.0
        self.hauteur_totale_m = 0.0
        self.materiau = "Fonte/Acier"
        self.contrainte_admissible_pa = 150e6 # Ex: 150 MPa

    def dimensionner(self, puissance_cible_w: float, pme_pa: float, regime_tr_min: float, nb_cylindres: int, ratio_course_alesage: float, pression_max_pa: float):
        """
        Déduit les dimensions du cylindre à partir des perfs cibles.
        P = PME * Vd * N / (2 si 4T)
        """
        if pme_pa <= 0 or regime_tr_min <= 0:
            raise ValueError("PME et Régime doivent être positifs")

        # 1. Calcul cylindrée totale requise pour la puissance
        # P = PME * V_tot * (n/60) / 2 (pour 4 temps)
        # V_tot = P * 120 / (PME * n)
        cylindree_totale_requise = (puissance_cible_w * 120) / (pme_pa * regime_tr_min)
        self.cylindree_unitaire_m3 = cylindree_totale_requise / nb_cylindres

        # 2. Déduction Alésage / Course
        # V = pi/4 * B^2 * S   et   S = ratio * B
        # V = pi/4 * ratio * B^3  =>  B = (4V / (pi*ratio))^(1/3)
        self.alesage_m = ( (4 * self.cylindree_unitaire_m3) / (math.pi * ratio_course_alesage) ) ** (1/3)
        self.course_m = self.alesage_m * ratio_course_alesage

        # 3. Épaisseur paroi (Pression max)
        self.epaisseur_paroi_m = calcul_epaisseur_cylindre_mince(pression_max_pa, self.alesage_m / 2, self.contrainte_admissible_pa)
        
        # 4. Hauteur estimée (Course + guidage jupe ~ 1.5*B + hauteur culasse/bas)
        self.hauteur_totale_m = self.course_m + (1.2 * self.alesage_m) 

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Alésage: {self.alesage_m*1000:.2f} mm\n"
                f"  - Course: {self.course_m*1000:.2f} mm\n"
                f"  - Cylindrée unitaire: {self.cylindree_unitaire_m3*1e6:.1f} cc\n"
                f"  - Épaisseur paroi: {self.epaisseur_paroi_m*1000:.2f} mm (pour Pmax={self.contrainte_admissible_pa/1e6:.0f}MPa adm)")
