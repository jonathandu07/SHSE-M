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


def test_resolve_metric_valeur_brute_reste_partielle():
    report = {"path": 42}

    res = resolve_metric(report, [{"raw_path": "path", "label": "x"}])

    assert res["value"] == 42
    assert res["status"] == "partial"
    assert res["confidence"] == "untraced_report_value"


def test_resolve_metric_computed_exige_trace_contractuelle():
    report = {
        "path": 42,
        "frontend": {"fields": [{"path": "path", "value": 42, "status": "computed"}]},
    }

    res = resolve_metric(report, [{"raw_path": "path", "label": "x"}])

    assert res["status"] == "partial"

    report["frontend"]["fields"][0]["trace"] = {"source": "formule"}
    traced = resolve_metric(report, [{"raw_path": "path", "label": "x"}])
    assert traced["status"] == "computed"
    assert traced["trace_present"] is True

def test_dashboard_metrics_exclut_les_valeurs_none():
    report = {
        "resume_gui": {
            "Architecture": "L4",
            "score_global_100": None # Missing
        }
    }
    res = adapt_backend_report(report)
    kpis = res["dashboard"]["kpis"]
    
    # Architecture should be in kpis
    arch = next((m for m in kpis if m["label"] == "Architecture"), None)
    assert arch is not None
    assert arch["value"] == "L4"
    
    # Score should NOT be in kpis if None
    score = next((m for m in kpis if m["label"] == "Score technique"), None)
    assert score is None

def test_missing_requirements_contient_les_valeurs_non_resolues():
    report = {
        "inconnues": {"critique": [{"nom": "Test", "raison": "Manquant"}]}
    }
    res = adapt_backend_report(report)
    assert len(res["missing_requirements"]) > 0

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
    subsystems = res["dashboard"]["subsystems"]
    batt = next((s for s in subsystems if s["name"] == "Batterie"), None)
    assert batt is not None
    assert "tension" in batt["resolved_data"]
    assert "resistance" not in batt["resolved_data"]
    assert batt["missing_count"] > 0

def test_raw_sections_conserve_les_inconnues():
    report = {"resume_gui": {"Bore_mm": None}}
    res = adapt_backend_report(report)
    # raw_sections is a list of dicts with name and value
    bore_section = next((s for s in res["raw_sections"] if s["name"] == "resume_gui"), None)
    assert bore_section is not None
    assert bore_section["value"]["Bore_mm"] is None

if __name__ == "__main__":
    try:
        test_resolve_metric_cherche_plusieurs_chemins_backend()
        test_dashboard_metrics_exclut_les_valeurs_none()
        test_missing_requirements_contient_les_valeurs_non_resolues()
        test_subsystem_card_affiche_seulement_valeurs_resolues()
        test_raw_sections_conserve_les_inconnues()
        print("All refined tests PASSED.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
