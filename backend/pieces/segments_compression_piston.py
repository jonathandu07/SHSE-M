import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_fuite_segment import calcul_debit_fuite_annulaire
from backend.modules.moteur_thermique.calcul_pertes_frottement import calcul_puissance_frottement_segment

class Piece:
    """Modèle calculable pour 'segments_compression_piston'."""

    def __init__(self):
        self.nom = "segments_compression_piston"
        self.nombre = 2
        self.epaisseur_axiale_m = 0.0
        self.largeur_radiale_m = 0.0
        self.jeu_coupe_m = 0.0003 # 0.3mm par défaut
        self.force_contact_n = 0.0
        self.puissance_frottement_w = 0.0
        self.debit_fuite_m3s = 0.0

    def dimensionner(self, piston, pression_max_pa: float, regime_tr_min: float):
        """
        Dépendances: Piston
        """
        # ISO 6621 standards approx
        # Epaisseur axiale ~ 0.015 * Bore à 0.04 * Bore (dépend technologies)
        # Pour automobile moderne: ~1.2mm à 2mm -> ~1.5% Alesage
        self.epaisseur_axiale_m = 0.015 * piston.diametre_m
        
        # Largeur radiale ~ D/25
        self.largeur_radiale_m = piston.diametre_m / 25.0
        
        # Force d'expansion (Tangential load) + Pression gaz arrière
        # P_contact = P_elastique + P_gaz
        pression_elastique = 0.2e6 # 0.2 MPa (tension segment)
        pression_contact_moy = pression_elastique + (0.5 * pression_max_pa) # Pression moyenne sur cycle
        
        aire_contact = math.pi * piston.diametre_m * self.epaisseur_axiale_m
        self.force_contact_n = pression_contact_moy * aire_contact
        
        # Pertes frottement
        # P = f * N * v
        # v = vitesse moyenne piston
        self.puissance_frottement_w = calcul_puissance_frottement_segment(
            force_normale_n=self.force_contact_n,
            vitesse_moyenne_ms=piston.vitesse_moyenne_ms,
            coef_frottement=0.1 # mixte/limite
        ) * self.nombre

        # Fuite (Simplifiée par la coupe)
        # On utilise fuite annulaire équivalente pour l'ordre de grandeur
        self.debit_fuite_m3s = calcul_debit_fuite_annulaire(
            delta_p_pa=pression_max_pa, # Pire cas
            jeu_radial_h_m=self.jeu_coupe_m / math.pi, # équivalent
            rayon_m=piston.diametre_m / 2,
            longueur_fuite_l_m=self.epaisseur_axiale_m * self.nombre,
            viscosite_dynamique_pa_s=1.8e-5 # Air chaud approx
        )

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Nombre: {self.nombre}\n"
                f"  - Epaisseur: {self.epaisseur_axiale_m*1000:.2f} mm\n"
                f"  - Frottement estimé: {self.puissance_frottement_w:.1f} W\n"
                f"  - Fuite max gaz: {self.debit_fuite_m3s*1e6:.2f} cm3/s")
