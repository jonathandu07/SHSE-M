import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_force_gaz import calcul_force_gaz
from backend.modules.moteur_thermique.calcul_force_inertie import calcul_force_inertie_alternative

class Piece:
    """Modèle calculable pour 'bielle_corps'."""

    def __init__(self):
        self.nom = "bielle_corps"
        self.entraxe_m = 0.0
        self.force_compression_max_n = 0.0
        self.force_traction_max_n = 0.0
        self.masse_totale_kg = 0.0 

    def dimensionner(self, cylindre, piston, axe_piston, pression_max_pa: float, regime_tr_min: float, ratio_lambda: float = 3.5):
        """
        Dépendances: Cylindre, Piston, AxePiston
        """
        rayon_manivelle = cylindre.course_m / 2
        self.entraxe_m = ratio_lambda * rayon_manivelle
        
        # Estimation masse bielle (Empirique: ~ Mass Piston * 1.5 pour acier)
        self.masse_totale_kg = piston.masse_kg * 1.5
        
        # Calcul masse alternative (Piston + Axe + ~1/3 Bielle)
        masse_alternative = piston.masse_kg + axe_piston.masse_kg + (self.masse_totale_kg / 3.0)
        
        # 1. Force Gaz Max (Compression)
        self.force_compression_max_n = calcul_force_gaz(pression_max_pa, cylindre.alesage_m)
        
        # 2. Force Inertie Max (Traction au PMH)
        self.force_traction_max_n = calcul_force_inertie_alternative(
            masse_alternative_kg=masse_alternative,
            rayon_manivelle_m=rayon_manivelle,
            vitesse_rotation_tr_min=regime_tr_min,
            longueur_bielle_m=self.entraxe_m,
            angle_vilebrequin_deg=0
        )

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Entraxe: {self.entraxe_m*1000:.2f} mm\n"
                f"  - Masse Est.: {self.masse_totale_kg*1000:.0f} g\n"
                f"  - Force Comp. Max: {self.force_compression_max_n/1000:.2f} kN\n"
                f"  - Force Trac. Max (Inertie): {self.force_traction_max_n/1000:.2f} kN")
