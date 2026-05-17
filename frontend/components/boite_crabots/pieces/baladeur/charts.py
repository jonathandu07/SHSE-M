# frontend/components/boite_crabots/pieces/baladeur/charts.py
from __future__ import annotations

from frontend.ensemble.viz_radar_template import plot_data
from backend.components.boite_crabots.pieces.baladeur import Baladeur

def afficher_radar(piece: Baladeur):
    """Affiche le graphique radar des métriques de la pièce."""
    # TODO: Extraire les données pertinentes du rapport de la pièce
    rapport = piece.analyser(strict=False)
    
    # Exemple de données
    data = {
        "Performance": 1.0,
        "Fiabilité": 1.0,
        "Poids": 1.0,
    }
    
    # Appel du template radar du frontend
    # plot_data(...) 
    pass
