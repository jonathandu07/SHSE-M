import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'systeme_rappel_precharge'.
    Ressorts de rappel de soupapes ou mécanismes Stirling.
    """

    def __init__(self):
        self.nom = "systeme_rappel_precharge"
        self.raideur_k_nm = 0.0
        self.force_rappel_max_n = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, masse_mobile_kg, rpm_max, course_m):
        """
        Calcule la raideur nécessaire pour assurer le rappel de la masse mobile
        avant le cycle suivant (limite d'affolement).
        F_rappel > M * A_max
        A_max ~ R * omega^2
        """
        # Accélération Max (Approx sinus)
        omega = (3.14159 * rpm_max) / 30.0
        accel_max = (course_m / 2.0) * (omega**2)
        
        # Force nécessaire (avec coeff sécurité 1.3 anti-affolement)
        force_dyn_req = masse_mobile_kg * accel_max * 1.3
        
        # On dimensionne le ressort pour fournir cette force à pleine ouverture
        self.force_rappel_max_n = force_dyn_req
        
        # Raideur K (si comprimé de 'course_m' + précharge)
        # K = F / (d + pre) -> Simplifié K = F / d (worst case raideur max)
        if course_m > 0:
            self.raideur_k_nm = self.force_rappel_max_n / course_m
        else:
            self.raideur_k_nm = 0.0
            
        # Estimation Masse Ressort (Energie élastique -> Volume Acier)
        # E = 0.5 * k * x^2
        energie_joules = 0.5 * self.raideur_k_nm * (course_m**2)
        # Densité énergétique ressort acier ~ 500-1000 J/kg ? Non, plutôt par volume de fil.
        # Formule empirique M ~ E / 100 (très approximatif)
        self.masse_kg = energie_joules * 0.005 # kg

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Force Rappel Max: {self.force_rappel_max_n:.1f} N\n"
                f"  - Raideur K: {self.raideur_k_nm/1000:.1f} N/mm\n"
                f"  - Masse: {self.masse_kg*1000:.1f} g")
