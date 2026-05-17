import sys
import os
sys.path.append(os.getcwd())
from backend.ensemble.carburant import get_carburant, get_pire_carburant, creer_melange

def test_fuels():
    essence = get_carburant("essence")
    print(f"Fuel: {essence.nom}, Energy Mix: {essence.energie_melange_stoechio_mj_kg():.2f} MJ/kg")
    
    pire = get_pire_carburant(objectif="puissance")
    print(f"Pire fuel pour la puissance: {pire.nom} ({pire.energie_melange_stoechio_mj_kg():.2f} MJ/kg)")
    
    # Test mélange E85
    e85 = creer_melange({"ethanol": 0.85, "essence": 0.15}, nom="E85")
    print(f"Mélange: {e85.nom}, PCI: {e85.pci_mj_kg:.2f} MJ/kg, AFR: {e85.afr_stoechiometrique:.2f}")

if __name__ == "__main__":
    try:
        test_fuels()
        print("Test Success")
    except Exception as e:
        print(f"Test Failed: {e}")
