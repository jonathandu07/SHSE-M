import sys
import os

# Ajout du chemin projet
sys.path.append(os.getcwd())

try:
    from backend.modules.systeme.analyse_puissance_sortie import optimiser_puissance_sortie
    from backend.main import _fuel_catalog
    
    print("Test de l'optimisation multi-carburant...")
    
    # On simule un appel avec multi-carburant
    res = optimiser_puissance_sortie(
        puissance=100000.0,
        unite="w",
        donnees_connues={"rpm_moteur": 3000.0},
        espace_recherche={
            "carburant": ["essence", "diesel"],
            "temps_moteur": [4],
            "type_puissance_moteur": ["frein"]
        }
    )
    
    if "selection" in res and "pire_cas_dimensionnant" in res["selection"]:
        print("SUCCÈS: Pire cas trouvé.")
        print(f"Détails: {res['selection']['pire_cas_dimensionnant']}")
    else:
        print("ÉCHEC: Pire cas non trouvé dans le rapport.")
        print(f"Rapport: {res}")

except Exception as e:
    print(f"ERREUR: {e}")
    import traceback
    traceback.print_exc()
