"""
Chemin : frontend/components/boite_crabots/pieces/roulement_boite/roulement_boite.py
But : Page d'affichage (orchestrateur) pour la pièce roulement_boite, agrégeant ses vues graphiques.
"""

from __future__ import annotations
import matplotlib.pyplot as plt

# Importations conditionnelles (si les modules existent)
try:
    from . import sketches_2d
    HAS_SKETCHES = True
except ImportError:
    HAS_SKETCHES = False

try:
    from . import charts
    HAS_CHARTS = True
except ImportError:
    HAS_CHARTS = False

def afficher_vues_roulement_boite():
    print("Affichage des modules graphiques pour la pièce : roulement_boite")
    
    # Si le module sketches_2d existe et a une fonction de tracé (à adapter selon vos fonctions réelles)
    # if HAS_SKETCHES and hasattr(sketches_2d, "tracer_croquis"):
    #     sketches_2d.tracer_croquis()
        
    # if HAS_CHARTS and hasattr(charts, "tracer_graphique"):
    #     charts.tracer_graphique()
        
    # plt.show()

if __name__ == "__main__":
    afficher_vues_roulement_boite()
