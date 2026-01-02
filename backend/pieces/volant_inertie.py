import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.boite_crabots.calcul_choc_engagement import calcul_energie_choc

class Piece:
    """Modèle calculable pour 'volant_inertie'."""

    def __init__(self):
        self.nom = "volant_inertie"
        self.inertie_kgm2 = 0.0
        self.diametre_externe_m = 0.0
        self.masse_kg = 0.0
        self.energie_stockee_j = 0.0
        self.irregularite_cycle = 0.01 # 1%

    def dimensionner(self, vilebrequin, puissance_cible_w: float, regime_tr_min: float, nb_cylindres: int):
        """
        Dépendances: Vilebrequin
        Dimensionnement pour lisser le couple (coefficient d'irrégularité delta).
        E_cinetique = 1/2 I w^2
        Delta_E = P * (60/N) * k_form e(pour absorber les pics de couple)
        I = Delta_E / (w^2 * delta)
        """
        omega = (2 * math.pi * regime_tr_min) / 60
        temps_cycle_s = 60 / regime_tr_min  * 2 # 4T
        energie_cycle = puissance_cible_w * (60/regime_tr_min) * (2 if nb_cylindres<2 else 1) # Approx
        
        # Energie à tamponner (estimation grossière pour 4 cyl: 10-20% energie tour)
        delta_e = energie_cycle * 0.2 
        
        if omega > 0:
            self.inertie_kgm2 = delta_e / ( (omega**2) * self.irregularite_cycle )
            self.energie_stockee_j = 0.5 * self.inertie_kgm2 * (omega**2)

        # Géométrie : Disque plein acier
        # I = 1/2 * m * r^2  => m = 2I / r^2
        # Densité acier 7800
        # On fixe un diamètre raisonnable par rapport à la course vilo (ex: 3x Course)
        rayon_max = vilebrequin.rayon_manivelle_m * 4 # Volant assez grand
        
        self.diametre_externe_m = rayon_max * 2
        
        # m = 2 * I / R^2
        if rayon_max > 0:
            self.masse_kg = (2 * self.inertie_kgm2) / (rayon_max**2)

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Inertie: {self.inertie_kgm2:.3f} kg.m2\n"
                f"  - Masse: {self.masse_kg:.1f} kg (Dia: {self.diametre_externe_m*1000:.0f}mm)\n"
                f"  - Energie @Nominal: {self.energie_stockee_j/1000:.1f} kJ")
