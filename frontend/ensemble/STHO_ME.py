"""
Chemin : frontend/ensemble/STHO_ME.py
But : Modèle global et orchestration du système STHO-ME.
"""

# frontend/ensemble/STHO_ME.py
from __future__ import annotations
import json

from frontend.main import get_backend_bridge
from frontend.ensemble.viz_radar_template import plot_data

def afficher_resultats_STHO_ME():
    """
    Récupère le rapport complet depuis frontend.main et 
    affiche uniquement la section concernant STHO_ME.
    """
    print("=== Lancement de l'analyse backend (100 kW par défaut) ===")
    bridge = get_backend_bridge()
    state = bridge.run_100kw()
    
    if not state.get("ok"):
        print("Erreur lors de l'exécution du backend.")
        print(state.get("status"))
        return

    ui_report = bridge.ui_report
    raw_report = bridge.raw_report
    
    print(f"\n--- Résultats pour le module STHO_ME ---")
    
    # Extraire la partie spécifique. 
    # TODO: Ajuster le chemin (ex: 'entrees', 'calculs', 'synthese') selon la logique métier de STHO_ME
    
    # Par exemple, chercher dans raw_sections si un mot clé correspond
    sections = ui_report.get("raw_sections", [])
    trouve = False
    for sec in sections:
        if "STHO_ME".lower() in str(sec.get("key")).lower():
            print(json.dumps(sec.get("data"), indent=2, ensure_ascii=False))
            trouve = True
            
    if not trouve:
        print("Aucune section spécifique pré-identifiée pour ce module dans le rapport brut.")
        print("Veuillez adapter le chemin d'extraction JSON dans ce script.")

    # Exemple d'intégration graphique si applicable
    # plot_data({ "Performance": 10 }, title="Radar STHO_ME")

if __name__ == "__main__":
    afficher_resultats_STHO_ME()
