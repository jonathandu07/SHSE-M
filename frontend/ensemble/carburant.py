"""
Chemin : frontend/ensemble/carburant.py
But : Définition des propriétés physico-chimiques et calculs liés aux carburants.
"""

# frontend/ensemble/carburant.py
from __future__ import annotations
import json

from frontend.main import get_backend_bridge
from frontend.ensemble.viz_radar_template import plot_data

def afficher_resultats_carburant():
    """
    Récupère le rapport complet depuis frontend.main et 
    affiche uniquement la section concernant carburant.
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
    
    print(f"\n--- Résultats pour le module carburant ---")
    
    # Extraire la partie spécifique. 
    # TODO: Ajuster le chemin (ex: 'entrees', 'calculs', 'synthese') selon la logique métier de carburant
    
    # Par exemple, chercher dans raw_sections si un mot clé correspond
    sections = ui_report.get("raw_sections", [])
    trouve = False
    for sec in sections:
        if "carburant".lower() in str(sec.get("key")).lower():
            print(json.dumps(sec.get("data"), indent=2, ensure_ascii=False))
            trouve = True
            
    if not trouve:
        print("Aucune section spécifique pré-identifiée pour ce module dans le rapport brut.")
        print("Veuillez adapter le chemin d'extraction JSON dans ce script.")

    # Exemple d'intégration graphique si applicable
    # plot_data({ "Performance": 10 }, title="Radar carburant")

if __name__ == "__main__":
    afficher_resultats_carburant()
