import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'butees_mecaniques_fin_de_course'.
    Protection fin de course (Silentblocs ou butées métalliques).
    """

    def __init__(self):
        self.nom = "butees_mecaniques_fin_de_course"
        self.energie_absorption_max_j = 0.0
        self.raideur_axial_kn_mm = 0.0
        self.masse_kg = 0.0

    def dimensionner(self, masse_mobile_kg, vitesse_impact_ms=1.0):
        """
        Dimensionne pour absorber l'énergie cinétique résiduelle en cas de dépassement de course.
        E = 0.5 * M * V^2
        """
        energie_cinetique = 0.5 * masse_mobile_kg * (vitesse_impact_ms**2)
        
        # On dimensionne pour absorber cette énergie avec déformation max de 5mm
        def_max_m = 0.005
        
        # E = 0.5 * K * x^2 => K = 2*E / x^2
        k_nm = (2 * energie_cinetique) / (def_max_m**2)
        
        self.energie_absorption_max_j = energie_cinetique
        self.raideur_axial_kn_mm = k_nm / 1e6 # kN/mm -> Non, N/m / 1e6 -> MN/m = kN/mm
        
        # Masse (Bloc élastomère + support acier)
        # Empirique: 100g par 100 Joules
        self.masse_kg = (energie_cinetique / 100.0) * 0.1
        if self.masse_kg < 0.05: self.masse_kg = 0.05

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Capacité Absorption: {self.energie_absorption_max_j:.1f} J\n"
                f"  - Raideur Choc: {self.raideur_axial_kn_mm:.1f} kN/mm\n"
                f"  - Masse: {self.masse_kg*1000:.0f} g")
