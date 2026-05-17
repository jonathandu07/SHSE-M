"""
Chemin : frontend/components/moteur_thermique/pieces/couvercle_cylindre/couvercle_cylindre.py
But : Page d'affichage (orchestrateur) pour la pièce couvercle_cylindre.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Configuration du sys.path pour accéder à frontend.main et backend
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from frontend.main import get_backend_bridge

# Import de la classe métier du backend
try:
    from backend.components.moteur_thermique.pieces.couvercle_cylindre import CouvercleCylindre
    HAS_BACKEND_CLASS = True
except ImportError:
    HAS_BACKEND_CLASS = False
    print("Avertissement : Impossible d'importer la classe CouvercleCylindre du backend.")

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
    from . import mesh_3d
    HAS_MESH = True
except ImportError:
    HAS_MESH = False

try:
    from . import views_3d
    HAS_VIEWS = True
except ImportError:
    HAS_VIEWS = False

def afficher_vues_couvercle_cylindre():
    print("=======================================================")
    print("  Affichage des vues pour : couvercle_cylindre")
    print("=======================================================")
    
    print("1. Initialisation du pont frontend-backend via frontend.main...")
    bridge = get_backend_bridge()
    state = bridge.run_100kw()
    report = state.get("raw_report", {})
    
    if not HAS_BACKEND_CLASS:
        print("Erreur : Classe métier introuvable. Affichage impossible.")
        return

    print("2. Instanciation de la pièce métier...")
    try:
        piece = CouvercleCylindre()
    except Exception as e:
        print(f"Erreur lors de l'instanciation de CouvercleCylindre : {e}")
        return

    print("3. Lancement des modules graphiques...")
    modules_trouves = 0

    if HAS_SKETCHES:
        # Recherche des fonctions d'affichage
        for func_name in ["afficher_2d", "afficher_croquis", "tracer_croquis"]:
            if hasattr(sketches_2d, func_name):
                print(f" -> Lancement de sketches_2d.{func_name}...")
                getattr(sketches_2d, func_name)(piece)
                modules_trouves += 1
                break

    if HAS_CHARTS:
        for func_name in ["afficher_radar", "afficher_graphique", "tracer_graphique"]:
            if hasattr(charts, func_name):
                print(f" -> Lancement de charts.{func_name}...")
                getattr(charts, func_name)(piece)
                modules_trouves += 1
                break

    if HAS_MESH:
        for func_name in dir(mesh_3d):
            if func_name.startswith("afficher_") and func_name.endswith("3d"):
                print(f" -> Lancement de mesh_3d.{func_name}...")
                func = getattr(mesh_3d, func_name)
                try:
                    func(piece)
                except Exception as e:
                    print(f"Erreur d'exécution de {func_name} : {e}")
                modules_trouves += 1
                break
        
    if HAS_VIEWS:
        for func_name in ["afficher_3d", "afficher_vues", "tracer_vues"]:
            if hasattr(views_3d, func_name):
                print(f" -> Lancement de views_3d.{func_name}...")
                getattr(views_3d, func_name)(piece)
                modules_trouves += 1
                break

    if modules_trouves == 0:
        print(" -> Aucun module graphique exécutable n'a été trouvé pour cette pièce.")
    else:
        print("Terminé.")

if __name__ == "__main__":
    afficher_vues_couvercle_cylindre()
