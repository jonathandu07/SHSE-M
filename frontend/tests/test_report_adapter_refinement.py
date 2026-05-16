import sys
import os
from typing import Any, Dict

# Add root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from frontend.gui.report_adapter import (
    adapt_backend_report, 
    resolve_metric,
    get_nested
)

def test_resolve_metric_cherche_plusieurs_chemins_backend():
    report = {
        "path2": 42,
        "path3": {"valeur": 100, "source": "test_source"}
    }
    
    # Test path 2
    res = resolve_metric(report, [
        {"raw_path": "path1"},
        {"raw_path": "path2"},
    ])
    assert res["value"] == 42
    assert res["resolved"] is True
    
    # Test path 3 (nested detail)
    res = resolve_metric(report, [
        {"raw_path": "path1"},
        {"raw_path": "path3"},
    ])
    assert res["value"] == 100
    assert res["source"] == "test_source"
    assert res["resolved"] is True

def test_dashboard_metrics_exclut_les_valeurs_none():
    report = {
        "resume_gui": {
            "Architecture": "L4",
            "N_cyl": None # Missing
        }
    }
    res = adapt_backend_report(report)
    
    # Architecture should be in dashboard_metrics
    arch = next((m for m in res["dashboard_metrics"] if m["label"] == "Architecture"), None)
    assert arch is not None
    assert arch["value"] == "L4"
    
    # N_cyl should NOT be in dashboard_metrics
    ncyl = next((m for m in res["dashboard_metrics"] if m["label"] == "Nombre de cylindres"), None)
    assert ncyl is None

def test_missing_requirements_contient_les_valeurs_non_resolues():
    report = {
        "resume_gui": {
            "Architecture": "L4",
            "N_cyl": None # Missing
        }
    }
    res = adapt_backend_report(report)
    
    # N_cyl should be in missing_requirements
    ncyl = next((m for m in res["missing_requirements"] if m["label"] == "Nombre de cylindres"), None)
    assert ncyl is not None
    assert ncyl["resolved"] is False

def test_subsystem_card_affiche_seulement_valeurs_resolues():
    report = {
        "analyses_composants": {
            "batterie_dimensionnement": {
                "tension": 400,
                "resistance": None
            }
        }
    }
    res = adapt_backend_report(report)
    batt = next((s for s in res["subsystems"] if s["name"] == "Batterie"), None)
    assert batt is not None
    assert "tension" in batt["resolved_data"]
    assert "resistance" not in batt["resolved_data"]
    assert batt["missing_count"] > 0

def test_unknowns_ne_sont_pas_affiches_comme_valeurs_dashboard():
    # Similar to test_dashboard_metrics_exclut_les_valeurs_none but explicit
    report = {"resume_gui": {"RPM": None}}
    res = adapt_backend_report(report)
    rpm = next((m for m in res["dashboard_metrics"] if m["label"] == "Régime nominal"), None)
    assert rpm is None
    
    missing_rpm = next((m for m in res["missing_requirements"] if m["label"] == "Régime nominal"), None)
    assert missing_rpm is not None

def test_raw_json_conserve_les_inconnues():
    report = {"resume_gui": {"Bore_mm": None}}
    res = adapt_backend_report(report)
    # The technical_audit (data_tree) should still have it
    bore_section = next((s for s in res["technical_audit"] if s["name"] == "resume_gui"), None)
    assert bore_section is not None
    assert bore_section["value"]["Bore_mm"] is None

if __name__ == "__main__":
    test_resolve_metric_cherche_plusieurs_chemins_backend()
    test_dashboard_metrics_exclut_les_valeurs_none()
    test_missing_requirements_contient_les_valeurs_non_resolues()
    test_subsystem_card_affiche_seulement_valeurs_resolues()
    test_unknowns_ne_sont_pas_affiches_comme_valeurs_dashboard()
    test_raw_json_conserve_les_inconnues()
    print("All refined tests PASSED.")
