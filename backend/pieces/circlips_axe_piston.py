import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'circlips_axe_piston'.
    Anneau élastique de retenue axiale pour l'axe de piston.
    """

    def __init__(self):
        self.nom = "circlips_axe_piston"
        self.diametre_nominal_m = 0.0
        self.epaisseur_mm = 0.0
        self.profondeur_gorge_mm = 0.0
        self.effort_cisaillement_max_n = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, axe_piston, rpm_max):
        """
        Dimensionne le circlip pour retenir l'axe soumis aux accélérations axiales parasites.
        """
        self.diametre_nominal_m = axe_piston.diametre_m
        
        # Standards DIN 472 approx
        if self.diametre_nominal_m < 0.020:
            self.epaisseur_mm = 1.0
            self.profondeur_gorge_mm = 0.7
        elif self.diametre_nominal_m < 0.040:
            self.epaisseur_mm = 1.2
            self.profondeur_gorge_mm = 1.0
        elif self.diametre_nominal_m < 0.100:
            self.epaisseur_mm = 1.5
            self.profondeur_gorge_mm = 1.5
        else:
            self.epaisseur_mm = 2.5
            self.profondeur_gorge_mm = 2.0
            
        # Calcul Effort Max admissible (Cisaillement)
        # Tau_admissible ~ 300 MPa (Acier ressort)
        # Surface cisaillement = pi * D * Profondeur
        surface_cisaillement = 3.14159 * self.diametre_nominal_m * (self.profondeur_gorge_mm / 1000.0)
        self.effort_cisaillement_max_n = surface_cisaillement * 300e6
        
        # Masse (Volume anneau)
        # S = pi * ((D+prof)^2 - D^2) / 4 ... approx pi * D * prof
        vol_approx = surface_cisaillement * (self.epaisseur_mm / 1000.0)
        self.masse_kg = vol_approx * 7850.0

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Pour Axe Ø: {self.diametre_nominal_m*1000:.1f} mm\n"
                f"  - Épaisseur: {self.epaisseur_mm} mm (Gorge {self.profondeur_gorge_mm} mm)\n"
                f"  - Capacité Retenue Axiale: {self.effort_cisaillement_max_n/1000:.1f} kN")
