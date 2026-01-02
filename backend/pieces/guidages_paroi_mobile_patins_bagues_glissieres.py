import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'guidages_paroi_mobile_patins_bagues_glissieres'.
    Bagues de guidage pour le piston translateur.
    """

    def __init__(self):
        self.nom = "guidages_paroi_mobile_patins_bagues_glissieres"
        self.diametre_m = 0.0
        self.largeur_guidage_total_mm = 0.0
        self.pression_contact_pa = 0.0

    def dimensionner(self, paroi_mobile, force_laterale_n=100.0):
        """
        Dimensionne la surface de guidage pour supporter les efforts latéraux.
        Effort latéral souvent faible dans Stirling (pression équilibrée), 
        sauf composante gravité ou désalignement.
        """
        self.diametre_m = paroi_mobile.diametre_externe_m
        
        # Pression admissible patins composites : 10-20 MPa
        P_adm = 10e6
        
        # Surface requise = F / P_adm
        # Surface proj = D * L
        L_mini = force_laterale_n / (self.diametre_m * P_adm)
        if L_mini < 0.010: L_mini = 0.010 # Min 10mm
        
        # On met souvent 2 bagues espacées
        self.largeur_guidage_total_mm = L_mini * 2.0 * 1000 # x2 pour sécurité + coeff
        
        if self.largeur_guidage_total_mm < 20.0: 
            self.largeur_guidage_total_mm = 20.0 # Min constructif
            
        # Recalcul Pression réelle
        aire_reelle = self.diametre_m * (self.largeur_guidage_total_mm/1000.0)
        self.pression_contact_pa = force_laterale_n / aire_reelle

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Guidage: 2 Bagues composites\n"
                f"  - Largeur Totale Portée: {self.largeur_guidage_total_mm:.1f} mm\n"
                f"  - Pression Contact: {self.pression_contact_pa/1e3:.1f} kPa (Charge latérale {self.pression_contact_pa*self.diametre_m*(self.largeur_guidage_total_mm/1000):.0f}N)")
