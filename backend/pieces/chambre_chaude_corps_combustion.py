import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import calcul_epaisseur_cylindre_mince
from backend.modules.moteur_thermique.calcul_loi_gaz_parfait import calcul_pression_gaz_parfait

class Piece:
    """Modèle calculable pour 'chambre_chaude_corps_combustion'.
    Réservoir soumis à haute pression et haute température.
    """

    def __init__(self):
        self.nom = "chambre_chaude_corps_combustion"
        self.volume_m3 = 0.0
        self.diametre_interne_m = 0.0
        self.epaisseur_paroi_m = 0.0
        self.temperature_service_k = 1000.0 # 727°C
        self.materiau = "Inconel/Acier Refractaire"

    def dimensionner(self, cylindre, pression_max_pa: float):
        """
        Dépendances: Cylindre (pour cohérence volume)
        """
        # Volume mort chambre chaude ~ 1/10 Cylindrée unitaire ?
        self.volume_m3 = cylindre.cylindree_unitaire_m3 * 0.2
        
        # Forme sphérique ou cylindrique. Cylindrique L=D
        # V = pi * D^2/4 * D = pi * D^3 / 4 => D = (4V/pi)^(1/3)
        import math
        self.diametre_interne_m = ( (4 * self.volume_m3) / math.pi ) ** (1/3)
        
        # Contrainte admissible chute avec la température
        # Inconel @ 700°C -> Sigma_adm ~ 150-200 MPa
        sigma_adm_chaud = 180e6 
        
        self.epaisseur_paroi_m = calcul_epaisseur_cylindre_mince(
            pression_pa=pression_max_pa,
            rayon_interne_m=self.diametre_interne_m / 2,
            contrainte_admissible_pa=sigma_adm_chaud
        )

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Volume: {self.volume_m3*1e6:.0f} cc\n"
                f"  - Diamètre Int: {self.diametre_interne_m*1000:.1f} mm\n"
                f"  - Epaisseur: {self.epaisseur_paroi_m*1000:.2f} mm (pour {self.temperature_service_k}K)")
