import json
from backend.modules.systeme.database import SecureDatabase

def export():
    db = SecureDatabase()
    res = db.load_main_report("latest")
    
    if not res:
        print("Aucun rapport trouvé dans la base de données pour 'latest'.")
        return

    with open("toutes_les_donnees_completes.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=4)
        
    print("Toutes les données ont été extraites avec succès dans 'toutes_les_donnees_completes.json' !")

if __name__ == "__main__":
    export()
