"""
Chemin : frontend/components/moteur_electrique/pieces/rotor_moteur_electrique/rotor_moteur_electrique.py
But : Page d'affichage (orchestrateur) pour la pièce rotor_moteur_electrique, utilisant frontend/main.py pour extraire les données.
"""

from __future__ import annotations
import sys
from pathlib import Path
import matplotlib.pyplot as plt

# Configuration du sys.path pour accéder à frontend.main
_THIS_FILE = Path(__file__).resolve()
# Remonter de 4 niveaux : fichier.py -> piece -> pieces -> composant -> components -> frontend -> SHSE-M
_PROJECT_ROOT = _THIS_FILE.parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from frontend.main import get_backend_bridge
    HAS_FRONTEND = True
except ImportError:
    HAS_FRONTEND = False
    print("Erreur : Impossible d'importer frontend.main. Vérifiez les chemins.")

# Importations conditionnelles des modules graphiques
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

try:
    from . import views_3d
    HAS_VIEWS = True
except ImportError:
    HAS_VIEWS = False

def afficher_vues_rotor_moteur_electrique():
    report = {}
    if HAS_FRONTEND:
        print("Initialisation du pont frontend-backend...")
        bridge = get_backend_bridge()
        print("Calcul du scénario par défaut (100 kW)...")
        state = bridge.run_100kw()
        report = state.get("raw_report", {})
    
    print("Affichage des modules graphiques pour la pièce : rotor_moteur_electrique")
    
    # Exécution des fonctions de tracé en leur passant le rapport complet (Zero-Invention)
    modules_trouves = 0
    if HAS_SKETCHES:
        for func_name in dir(sketches_2d):
            if func_name.startswith("tracer"):
                func = getattr(sketches_2d, func_name)
                if callable(func):
                    modules_trouves += 1
                    try:
                        func(report)
                    except TypeError:
                        func() # Rétrocompatibilité si la fonction ne prend pas d'arguments
                        
    if HAS_CHARTS:
        for func_name in dir(charts):
            if func_name.startswith("tracer"):
                func = getattr(charts, func_name)
                if callable(func):
                    modules_trouves += 1
                    try:
                        func(report)
                    except TypeError:
                        func()
                        
    if HAS_VIEWS:
        for func_name in dir(views_3d):
            if func_name.startswith("tracer"):
                func = getattr(views_3d, func_name)
                if callable(func):
                    modules_trouves += 1
                    try:
                        func(report)
                    except TypeError:
                        func()

    if modules_trouves > 0:
        plt.show()
    else:
        print("Aucun module graphique exécutable n'a été trouvé pour cette pièce.")

if __name__ == "__main__":
    afficher_vues_rotor_moteur_electrique()
