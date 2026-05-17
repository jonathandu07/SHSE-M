# frontend/components/batterie/pieces/tms_batterie/charts.py
from __future__ import annotations

from frontend.ensemble.viz_radar_template import plot_data
from backend.components.batterie.pieces.tms_batterie import TmsBatterie

def afficher_radar(piece: TmsBatterie):
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
