import pprint
import traceback
import sys
import os
import json
from backend.main import dimensionner_systeme_shsem

if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].endswith(".json"):
        print("Erreur: veuillez fournir un fichier JSON d'entrée afin de définir les paramètres (tout est calculé, pas de valeurs par défaut).")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        kwargs = json.load(f)

    try:
        from backend.modules.systeme.database import SecureDatabase
        db = SecureDatabase()
        
        # Ce single call va:
        # 1. Appeler dimensionner_systeme_shsem(**kwargs)
        # 2. Tout sauvegarder dans shse_technical_data.db (y compris rapports_pieces)
        db_result = db.compute_and_save_from_main(report_name="latest", **kwargs)
        
        # On peut charger le rapport complet depuis la base
        res = db.load_main_report(report_name="latest")
        
        optim = res.get("optimisation", {})
        rapports_pieces = res.get("rapports_pieces", {})
        donnees_pieces = res.get("toutes_les_donnees_pieces", {})

        with open("dump_pieces_v2_output.txt", "w", encoding="utf-8") as f:
            f.write("=== STATUT DATABASE ===\n")
            f.write(f"Enregistrements chiffrés : {db_result.get('records_saved')}\n\n")

            f.write("=== INCONNUES OPTIMISATION ===\n")
            f.write(pprint.pformat(optim.get("inconnues", {})))
            
            f.write("\n\n=== PIECES (RAPPORTS D'ANALYSE) ===\n")
            for name, r in rapports_pieces.items():
                f.write(f"\n--- {name} ---\n")
                if isinstance(r, dict):
                    f.write(f"Inconnues Impossibles: {[i.get('nom') for i in r.get('inconnues', {}).get('impossibles', [])]}\n")
                    f.write(f"Inconnues Partielles: {[i.get('nom') for i in r.get('inconnues', {}).get('partielles', [])]}\n")
                    f.write("\n   --- Dimensions Calculees ---\n")
                    f.write(pprint.pformat(r.get("dimensions", {})))
                    f.write("\n")
                else:
                    f.write("Erreur : Le rapport n'est pas un dictionnaire.\n")

        print("Traitement terminé et sauvegardé dans backend/shse_technical_data.db. Voir dump_pieces_v2_output.txt")

    except Exception as e:
        with open("dump_pieces_v2_output.txt", "w", encoding="utf-8") as f:
            f.write("ERREUR FATALE DANS dimensionner_systeme_shsem:\n")
            f.write(traceback.format_exc() + "\n")
        print(f"Erreur fatale, vérifiez dump_pieces_v2_output.txt: {e}")
