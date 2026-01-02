import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.boite_crabots.calcul_dimensionnement_arbre import calcul_contrainte_cisaillement_torsion, calcul_contrainte_flexion_arbre, calcul_von_mises_arbre

class Piece:
    """Modèle calculable pour 'arbre_sortie_portee_sortie'."""

    def __init__(self):
        self.nom = "arbre_sortie_portee_sortie"
        self.diametre_m = 0.0
        self.longueur_m = 0.3 # Hypothèse
        self.contrainte_vm_max_pa = 0.0

    def dimensionner(self, couple_max_nm: float, force_radiale_engrenage_n: float):
        # Pré-dimensionnement à la torsion pure pour commencer
        # Tau = 16 T / (pi d^3)  => d = (16 T / (pi * Tau_adm))^(1/3)
        # Si Tau_adm = 100 MPa
        tau_adm = 100e6
        self.diametre_m = ((16 * couple_max_nm) / (math.pi * tau_adm)) ** (1/3)
        
        # Vérification complète avec Flexion (Moment M = F * L/4 approx milieu)
        moment_flechissant = force_radiale_engrenage_n * (self.longueur_m / 4)
        
        sigma_f = calcul_contrainte_flexion_arbre(moment_flechissant, self.diametre_m)
        tau_t = calcul_contrainte_cisaillement_torsion(couple_max_nm, self.diametre_m)
        
        self.contrainte_vm_max_pa = calcul_von_mises_arbre(sigma_f, tau_t)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Diamètre: {self.diametre_m*1000:.2f} mm\n"
                f"  - Contrainte VM Max: {self.contrainte_vm_max_pa/1e6:.1f} MPa")
