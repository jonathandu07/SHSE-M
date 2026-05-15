# test_backend_call.py
import sys
import os

# CONFIGURATION DU PATH
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

try:
    from backend.main import dimensionner_systeme_shsem
    from backend.modules.systeme.analyse_puissance_sortie import normaliser_puissance
    
    print("--- Test 150 kW ---")
    p_val = 150.0
    p_unit = "kw"
    norm = normaliser_puissance(p_val, p_unit)
    p_kw = norm.get("kw")
    print(f"Normalisation: {p_val} {p_unit} -> {p_kw} kW")
    
    # Simulate do_math logic
    backend_args = {
        "puissance_traction_kw": p_kw,
    }
    print(f"Appel backend avec: {backend_args}")
    # report = dimensionner_systeme_shsem(**backend_args)
    # print("Succès appel backend")

    print("\n--- Test 150 ch ---")
    p_val = 150.0
    p_unit = "ch"
    norm = normaliser_puissance(p_val, p_unit)
    p_kw = norm.get("kw")
    print(f"Normalisation: {p_val} {p_unit} -> {p_kw} kW")
    
    backend_args = {
        "puissance_traction_kw": p_kw,
    }
    print(f"Appel backend avec: {backend_args}")

except Exception as e:
    print(f"Erreur: {e}")
