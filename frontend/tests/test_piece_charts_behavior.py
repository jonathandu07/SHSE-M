from __future__ import annotations

import json

import pytest

from frontend.components.moteur_thermique.pieces.arbre_piston.charts import build_chart_contracts
from frontend.components.moteur_thermique.pieces.piston.charts import build_chart_contracts as build_piston_chart_contracts
from frontend.ensemble.graph_rendering import build_chart_figure, expected_quantities_for_piece, validate_chart_contracts


def test_charts_retournent_missing_required_sans_points_backend():
    charts = build_chart_contracts(global_report={"rapports_pieces": {"arbre_piston": {"piece": "arbre_piston"}}})

    json.dumps(charts, ensure_ascii=False)
    assert charts[0]["status"] == "missing_required"
    assert charts[0]["series"] == []
    assert charts[0]["missing_fields"]


def test_charts_affichent_series_backend_sans_generer_points():
    report = {
        "mechanical_graphs": {
            "graphiques": [
                {
                    "id": "arbre_piston_torsion",
                    "piece": "arbre_piston",
                    "title": "Torsion arbre piston",
                    "x_label": "Diametre (mm)",
                    "y_label": "Contrainte (MPa)",
                    "series": [{"name": "backend", "points": [{"x": 20, "y": 180}, {"x": 25, "y": 120}]}],
                }
            ]
        }
    }

    charts = build_chart_contracts(global_report=report)

    assert charts[0]["status"] == "partial"
    assert charts[0]["series"][0]["points"] == [{"x": 20, "y": 180}, {"x": 25, "y": 120}]


def test_build_chart_figure_refuse_graphique_sans_points():
    with pytest.raises(ValueError):
        build_chart_figure({"id": "empty", "series": []})


def test_chart_readiness_refuse_series_partielle_ou_candidate():
    readiness = validate_chart_contracts(
        [
            {"id": "partiel", "status": "partial", "series": [{"points": [{"x": 1, "y": 2}]}]},
            {"id": "candidat", "status": "candidate_from_power_profile", "series": [{"points": [{"x": 1, "y": 2}]}]},
        ]
    )

    assert readiness["status"] == "partial"
    with pytest.raises(ValueError):
        build_chart_figure({"id": "candidat", "status": "candidate_from_power_profile", "series": [{"points": [{"x": 1, "y": 2}]}]})


def test_charts_manquants_exposent_grandeurs_attendues_piece_critique():
    charts = build_piston_chart_contracts(global_report={"rapports_pieces": {"piston": {"piece": "piston"}}})

    assert charts[0]["status"] == "missing_required"
    assert "effort_gaz" in charts[0]["expected_quantities"]
    assert "jeu_radial" in charts[0]["expected_quantities"]
    assert all(item["path"].startswith("mechanical_graphs.graphiques") for item in charts[0]["missing_fields"])


def test_chart_backend_trace_infer_quantity_family_sans_generer_points():
    report = {
        "mechanical_graphs": {
            "graphiques": [
                {
                    "id": "piston_effort_gaz",
                    "piece": "piston",
                    "title": "Effort gaz piston",
                    "status": "computed",
                    "trace": {"producer": "backend"},
                    "x_label": "Angle (deg)",
                    "y_label": "Force (N)",
                    "series": [{"name": "backend", "points": [{"x": 0, "y": 10}, {"x": 1, "y": 11}]}],
                }
            ]
        }
    }

    charts = build_piston_chart_contracts(global_report=report)

    assert charts[0]["status"] == "computed"
    assert charts[0]["quantity_family"] == "effort_gaz"
    assert charts[0]["series"][0]["points"] == [{"x": 0, "y": 10}, {"x": 1, "y": 11}]
    assert "frottement" in expected_quantities_for_piece("piston")
