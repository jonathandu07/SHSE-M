import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'joint_tournant_arbre_sortie'.
    Joint à lèvre (SPI) pour étanchéité huile sur arbre de sortie.
    """

    def __init__(self):
        self.nom = "joint_tournant_arbre_sortie"
        self.diametre_arbre_m = 0.0
        self.diametre_exterieur_m = 0.0
        self.largeur_mm = 0.0
        self.vitesse_lineaire_ms = 0.0
        self.puissance_frottement_w = 0.0

    def dimensionner(self, arbre_sortie, rpm_max):
        """
        Dimensionne le joint SPI et estime la puissance perdue par frottement.
        """
        self.diametre_arbre_m = arbre_sortie.diametre_m
        if self.diametre_arbre_m == 0: self.diametre_arbre_m = 0.04 # fallback
        
        # Standards ISO 6194
        # E.g. d=40 -> D=62, B=10
        self.diametre_exterieur_m = self.diametre_arbre_m + 0.020 # +20mm au diamètre
        self.largeur_mm = 10.0 # Standard
        
        # Vitesse Linéaire
        omega = (3.14159 * rpm_max) / 30.0
        self.vitesse_lineaire_ms = (self.diametre_arbre_m / 2.0) * omega
        
        # Puissance Frottement (P = F * V)
        # F_frottement approx: 100 à 400 N/m circonférence selon pression contact
        # Prenons 150 N/m
        force_frottement_n = 150.0 * (3.14159 * self.diametre_arbre_m)
        self.puissance_frottement_w = force_frottement_n * self.vitesse_lineaire_ms

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Dimensions: Ø{self.diametre_arbre_m*1000:.1f} x Ø{self.diametre_exterieur_m*1000:.1f} x {self.largeur_mm} mm\n"
                f"  - Vitesse Périphérique: {self.vitesse_lineaire_ms:.1f} m/s\n"
                f"  - Pertes Frottement: {self.puissance_frottement_w:.1f} W")
