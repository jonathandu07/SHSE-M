import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SecureDatabase

def main():
    print("=== LECTURE DE LA BASE DE DONNÉES SÉCURISÉE ===\n")
    
    db = SecureDatabase()
    
    # Lecture d'une pièce spécifique
    print("Lecture de 'piston_puissance'...")
    data_piston = db.get_piece_data('piston_puissance')
    if data_piston:
        print("Données déchiffrées :")
        for k, v in data_piston.items():
            print(f"  - {k}: {v}")
    else:
        print("Erreur: Piston introuvable.")

    print("\nLecture de 'vilebrequin_corps'...")
    data_vilo = db.get_piece_data('vilebrequin_corps')
    if data_vilo:
        print(f"  - Couple Max: {data_vilo.get('couple_max_approx_nm', 'N/A')}")

if __name__ == "__main__":
    main()
