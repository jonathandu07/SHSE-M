import sys
import os
from typing import Any, Dict

# Add root to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from frontend.gui.report_adapter import (
    adapt_backend_report, 
    flatten_unknowns,
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


def test_missing_count_utilise_inconnues_consolidees_sans_doublons():
    unknown = {"nom": "rpm_moteur", "raison": "Requis pour le couple."}
    report = {
        "inconnues": {"partielles": [unknown]},
        "stho_me": {"inconnues": {"partielles": [unknown]}},
        "rapports": {
            "stho_me": {
                "resolution_inconnues": {"inconnues": {"partielles": [unknown]}},
                "inconnues": {"partielles": [unknown]},
            }
        },
        "optimisation": {
            "meilleur_resultat": {
                "analyse": {"resolution_inconnues": {"inconnues": {"partielles": [unknown]}}}
            }
        },
    }

    res = adapt_backend_report(report)

    assert len(res["missing_requirements"]) == 1
    assert res["dashboard"]["summary"]["missing_count"] == 1
    assert res["missing_requirements"][0]["label"] == "rpm_moteur"


def test_missing_count_ignore_cotes_preparation_solidworks_non_consolidees():
    report = {
        "rapports_pieces": {
            "piston": {
                "piece": "piston",
                "dossier_definition_solidworks": {
                    "statut": "partial",
                    "solidworks_ready": False,
                    "step_generation": False,
                    "schema_only": True,
                    "final_geometry": False,
                    "cotes_connues": {"diametre_exterieur_m": 0.08},
                    "cotes_manquantes": {"hauteur_m": None, "gorge_joint": None},
                    "tolerances": [
                        {"nom": "jeu_radial", "valeur": None, "statut": "missing"},
                    ],
                },
            }
        }
    }

    res = adapt_backend_report(report)

    assert res["dashboard"]["summary"]["missing_count"] == 0
    assert res["missing_requirements"] == []


def test_piece_list_expose_dossier_definition_solidworks_sans_inventer_cao():
    report = {
        "rapports_pieces": {
            "coussinet_arbre_piston": {
                "piece": "coussinet_arbre_piston",
                "dossier_definition_solidworks": {
                    "statut": "partial",
                    "solidworks_ready": True,
                    "step_generation": True,
                    "schema_only": True,
                    "final_geometry": True,
                    "cotes_connues": {"diametre_interieur_m": 0.022},
                    "cotes_manquantes": {"longueur_m": {"raison": "non fournie"}},
                    "interfaces_assemblage": [{"piece_b": "arbre_piston", "type_liaison": "palier_lisse", "statut": "partial"}],
                    "jeux_ajustements": [{"nom": "jeu_radial", "statut": "missing_required"}],
                    "contraintes_rdm": [{"nom": "pression_projetee"}],
                    "inconnues_bloquantes": [{"nom": "materiau_coussinet"}],
                },
            }
        }
    }

    res = adapt_backend_report(report)
    piece = next(item for item in res["pieces"] if item["name"] == "coussinet_arbre_piston")
    definition = piece["solidworks_definition"]

    assert definition["statut"] == "partial"
    assert definition["solidworks_ready"] is False
    assert definition["backend_solidworks_ready"] is True
    assert definition["step_generation"] is False
    assert definition["step_export"] is False
    assert definition["final_geometry"] is False
    assert definition["counts"]["cotes_connues"] == 1
    assert definition["counts"]["cotes_manquantes"] == 1
    assert definition["counts"]["interfaces"] == 1
    assert definition["counts"]["jeux_ajustements"] == 1
    assert definition["counts"]["contraintes_rdm"] == 1
    assert definition["counts"]["inconnues_bloquantes"] == 1
    assert res["dashboard"]["summary"]["missing_count"] == 0


def test_flatten_unknowns_garde_un_fallback_recursif_sans_racine():
    report = {
        "stho_me": {
            "inconnues": {
                "partielles": [{"nom": "tension_bus_dc_v", "raison": "Requise pour le courant."}]
            }
        }
    }

    unknowns = flatten_unknowns(report)

    assert len(unknowns) == 1
    assert unknowns[0]["name"] == "tension_bus_dc_v"

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
