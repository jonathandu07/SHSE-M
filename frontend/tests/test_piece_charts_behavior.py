from __future__ import annotations

import json

import pytest

from frontend.components.moteur_thermique.pieces.arbre_piston.charts import build_chart_contracts
from frontend.ensemble.graph_rendering import build_chart_figure


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

    assert charts[0]["status"] in {"available", "partial"}
    assert charts[0]["series"][0]["points"] == [{"x": 20, "y": 180}, {"x": 25, "y": 120}]


def test_build_chart_figure_refuse_graphique_sans_points():
    with pytest.raises(ValueError):
        build_chart_figure({"id": "empty", "series": []})
