import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import calcul_epaisseur_cylindre_mince

class Piece:
    """Modèle calculable pour 'chambre_froide_corps_refroidissement'.
    """

    def __init__(self):
        self.nom = "chambre_froide_corps_refroidissement"
        self.volume_m3 = 0.0
        self.diametre_interne_m = 0.0
        self.epaisseur_paroi_m = 0.0
        self.temperature_service_k = 350.0 # 77°C

    def dimensionner(self, cylindre, pression_max_pa: float):
        """
        Dépendances: Cylindre
        """
        # Volume similaire ou plus grand que chambre chaude
        self.volume_m3 = cylindre.cylindree_unitaire_m3 * 0.3
        
        # Géométrie Cylindrique
        import math
        self.diametre_interne_m = ( (4 * self.volume_m3) / math.pi ) ** (1/3)
        
        # Alu ou Acier standard car froid
        sigma_adm = 200e6 
        
        self.epaisseur_paroi_m = calcul_epaisseur_cylindre_mince(
            pression_pa=pression_max_pa,
            rayon_interne_m=self.diametre_interne_m / 2,
            contrainte_admissible_pa=sigma_adm
        )

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Volume: {self.volume_m3*1e6:.0f} cc\n"
                f"  - Epaisseur: {self.epaisseur_paroi_m*1000:.2f} mm")
