"""
Chemin : frontend/ensemble/strategie_energie.py
But : Définition et calcul des stratégies de gestion de l'énergie.
"""

# frontend/ensemble/strategie_energie.py
from __future__ import annotations
import json

from frontend.main import get_backend_bridge
from frontend.ensemble.viz_radar_template import plot_data

def afficher_resultats_strategie_energie():
    """
    Récupère le rapport complet depuis frontend.main et 
    affiche uniquement la section concernant strategie_energie.
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
    
    print(f"\n--- Résultats pour le module strategie_energie ---")
    
    # Extraire la partie spécifique. 
    # TODO: Ajuster le chemin (ex: 'entrees', 'calculs', 'synthese') selon la logique métier de strategie_energie
    
    # Par exemple, chercher dans raw_sections si un mot clé correspond
    sections = ui_report.get("raw_sections", [])
    trouve = False
    for sec in sections:
        if "strategie_energie".lower() in str(sec.get("key")).lower():
            print(json.dumps(sec.get("data"), indent=2, ensure_ascii=False))
            trouve = True
            
    if not trouve:
        print("Aucune section spécifique pré-identifiée pour ce module dans le rapport brut.")
        print("Veuillez adapter le chemin d'extraction JSON dans ce script.")

    # Exemple d'intégration graphique si applicable
    # plot_data({ "Performance": 10 }, title="Radar strategie_energie")

if __name__ == "__main__":
    afficher_resultats_strategie_energie()
