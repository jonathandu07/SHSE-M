import sys
import os
from typing import Any, Dict

# Add frontend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from gui.report_adapter import (
    adapt_backend_report, 
    flatten_unknowns, 
    flatten_alerts,
    get_nested
)

def test_scenario_1_empty():
    print("Test 1: Empty report")
    res = adapt_backend_report({})
    assert "error" in res or res.get("is_empty") is True
    print("OK")

def test_scenario_2_resume_gui():
    print("Test 2: Only resume_gui")
    report = {"resume_gui": {"Architecture": "L4", "N_cyl": 4}}
    res = adapt_backend_report(report)
    items = res["sections"]["resume"]["items"]
    arch = next(i for i in items if i["label"] == "Architecture")
    assert arch["value"] == "L4"
    assert arch["raw_path"] == "resume_gui.Architecture"
    print("OK")

def test_scenario_3_details():
    print("Test 3: derivees_chaine_energie.details")
    report = {"derivees_chaine_energie": {"details": {"p_traction_w": 50000}}}
    res = adapt_backend_report(report)
    items = res["sections"]["energie"]["items"]
    p_trac = next(i for i in items if i["label"] == "Puissance Traction")
    assert p_trac["value"] == 50000
    print("OK")

def test_scenario_4_strategie():
    print("Test 4: strategie_energie.bilan_bus_dc")
    report = {"strategie_energie": {"bilan_bus_dc": {"puissance_recharge_retenue_w": 20000}}}
    res = adapt_backend_report(report)
    items = res["sections"]["energie"]["items"]
    p_rech = next(i for i in items if i["label"] == "Recharge Batterie")
    assert p_rech["value"] == 20000
    print("OK")

def test_scenario_8_unknowns():
    print("Test 8: Unknowns (impossibles + partielles)")
    report = {
        "inconnues": {
            "impossibles": [{"nom": "Test", "raison": "Blocked"}],
            "partielles": [{"champ": "Param", "raison": "Missing"}]
        }
    }
    unknowns = flatten_unknowns(report)
    assert len(unknowns) == 2
    assert unknowns[0]["name"] == "Test"
    assert unknowns[1]["name"] == "Param"
    print("OK")

def test_scenario_9_alerts():
    print("Test 9: Alerts")
    report = {
        "alertes": {
            "systeme": [{"nom": "Warning", "detail": "Low fuel"}]
        }
    }
    alerts = flatten_alerts(report)
    assert len(alerts) == 1
    assert alerts[0]["name"] == "Warning"
    print("OK")

def test_scenario_12_none_stays_none():
    print("Test 12: None stays None (None != 0)")
    report = {"resume_gui": {"Bore_mm": None}}
    res = adapt_backend_report(report)
    items = res["sections"]["resume"]["items"]
    bore = next(i for i in items if i["label"] == "Alésage")
    assert bore["value"] is None
    assert bore["status"] == "inconnu"
    print("OK")

def test_scenario_13_no_zero_fallback():
    print("Test 13: No 0 fallback")
    report = {"resume_gui": {}} # Missing key
    res = adapt_backend_report(report)
    items = res["sections"]["resume"]["items"]
    bore = next(i for i in items if i["label"] == "Alésage")
    assert bore["value"] is None
    print("OK")

def run_all_tests():
    try:
        test_scenario_1_empty()
        test_scenario_2_resume_gui()
        test_scenario_3_details()
        test_scenario_4_strategie()
        test_scenario_8_unknowns()
        test_scenario_9_alerts()
        test_scenario_12_none_stays_none()
        test_scenario_13_no_zero_fallback()
        print("\nAll implemented tests PASSED.")
    except AssertionError as e:
        print(f"\nTEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR DURING TESTS: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
