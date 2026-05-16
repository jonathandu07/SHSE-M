import sys
import os
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from frontend.gui.report_adapter import adapt_backend_report
from frontend.gui.components import COLORS, PALETTE

def test_dashboard_ne_contient_pas_liste_inconnues_complete():
    report = {
        "meta": {"nom_projet": "TEST"},
        "inconnues": {"critique": [{"nom": "X", "raison": "Y"}]}
    }
    ui = adapt_backend_report(report)
    # Dans la nouvelle structure, dashboard ne contient pas de liste 'unknowns'
    assert "unknowns" not in ui["dashboard"]
    # Les inconnues sont dans missing_requirements au top level
    assert len(ui["missing_requirements"]) > 0

def test_dashboard_metrics_exclut_none():
    report = {
        "resume_gui": {"Bore_mm": None, "Architecture": "L4"}
    }
    ui = adapt_backend_report(report)
    kpis = ui["dashboard"]["kpis"]
    # Bore_mm est None, donc il ne doit pas être dans les KPIs du dashboard
    labels = [m["label"] for m in kpis]
    assert "Alésage" not in labels
    assert "Architecture" in labels

def test_missing_requirements_recoit_inconnues():
    report = {
        "inconnues": {"critique": [{"nom": "Donnée Cruciale", "raison": "Manquante"}]}
    }
    ui = adapt_backend_report(report)
    missing = ui["missing_requirements"]
    assert any(m["name"] == "Donnée Cruciale" for m in missing)

def test_system_data_ne_rend_pas_dict_en_ligne_unique():
    # Test conceptuel : format_value ne doit pas transformer un dict en chaîne géante
    from frontend.gui.components import format_value
    val = {"a": 1, "b": 2}
    formatted = format_value(val)
    assert "[2 items]" in formatted
    assert "{" not in formatted

def test_architecture_candidates_extraits_depuis_backend():
    report = {
        "systeme_complet": {
            "synthese": {
                "architectures_candidates": [{"nom": "L4", "score": 90}]
            }
        }
    }
    ui = adapt_backend_report(report)
    assert len(ui["architecture_candidates"]) == 1
    assert ui["architecture_candidates"][0]["nom"] == "L4"

def test_palette_hex_uniquement_autorisee():
    # Vérifie que PALETTE contient uniquement les 5 couleurs autorisées
    authorized = {"#F4FEFE", "#091226", "#75161E", "#0A0B0A", "#3E5349"}
    for color_hex in PALETTE.values():
        assert color_hex in authorized

if __name__ == "__main__":
    try:
        test_dashboard_ne_contient_pas_liste_inconnues_complete()
        test_dashboard_metrics_exclut_none()
        test_missing_requirements_recoit_inconnues()
        test_system_data_ne_rend_pas_dict_en_ligne_unique()
        test_architecture_candidates_extraits_depuis_backend()
        test_palette_hex_uniquement_autorisee()
        print("UI INTEGRITY TESTS PASSED.")
    except AssertionError as e:
        print(f"UI INTEGRITY TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR DURING UI INTEGRITY TESTS: {e}")
        sys.exit(1)
