import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class Piece:
    """Modèle calculable pour 'brides_supports'.
    Éléments de fixation structurelle (périphériques, tubulures).
    """

    def __init__(self):
        self.nom = "brides_supports"
        self.masse_totale_kg = 0.0
        self.nombre_points_ancrage = 0

    def dimensionner(self, masse_totale_moteur_estimee_kg):
        """
        Estime la masse des supports nécessaires pour tenir le moteur ou ses périphériques.
        Empirique: ~ 2-5% de la masse totale du moteur pour les fixations/brides externes.
        """
        # On suppose que cette classe représente l'ensemble de la visserie de support
        # ou les pattes de fixation au châssis.
        
        ratio_structure = 0.03 # 3%
        self.masse_totale_kg = masse_totale_moteur_estimee_kg * ratio_structure
        
        # Nombre de points d'ancrage iso-statiques ou hyperstatiques
        if masse_totale_moteur_estimee_kg < 100:
            self.nombre_points_ancrage = 3
        else:
            self.nombre_points_ancrage = 4

    def decrire(self) -> str:
        return (f"Pièce: {self.nom}\n"
                f"  - Points Ancrage: {self.nombre_points_ancrage}\n"
                f"  - Masse Est. Supports: {self.masse_totale_kg:.1f} kg (Ratio 3%)")
