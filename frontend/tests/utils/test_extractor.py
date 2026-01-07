import os
import sys

# Ajout du chemin racine pour les imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from frontend.tests.utils.data_extractor import get_latest_system_analysis

def test_extraction():
    log_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend", "logs", "test_systeme_complet.log"))
    print(f"Test d'extraction sur : {log_path}")
    
    data = get_latest_system_analysis(log_path)
    if data:
        print("SUCCESS: Données extraites avec succès.")
        print(f"Nombre de sous-systèmes : {len(data.get('sous_systemes', {}))}")
        if "moteur_thermique" in data.get("sous_systemes", {}):
            print("OK: 'moteur_thermique' trouvé dans les données.")
        else:
            print("WARNING: 'moteur_thermique' absent des sous-systèmes.")
    else:
        print("FAILED: Aucune donnée extraite.")

if __name__ == "__main__":
    test_extraction()
