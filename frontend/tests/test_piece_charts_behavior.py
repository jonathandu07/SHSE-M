from __future__ import annotations

import json

import pytest

from frontend.components.moteur_thermique.pieces.arbre_piston.charts import build_chart_contracts
from frontend.components.moteur_thermique.pieces.arbre_vilebrequin.charts import build_chart_contracts as build_arbre_vilebrequin_chart_contracts
from frontend.components.moteur_thermique.pieces.coussinet_arbre_piston.charts import build_chart_contracts as build_coussinet_chart_contracts
from frontend.components.moteur_thermique.pieces.joint_deplaceur.charts import build_chart_contracts as build_joint_deplaceur_chart_contracts
from frontend.components.moteur_thermique.pieces.piston.charts import build_chart_contracts as build_piston_chart_contracts
from frontend.components.moteur_thermique.pieces.roulement_aiguille_arbre.charts import build_chart_contracts as build_roulement_arbre_chart_contracts
from frontend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin.charts import build_chart_contracts as build_roulement_vilebrequin_chart_contracts
from frontend.components.moteur_thermique.pieces.vilbrequin.charts import build_chart_contracts as build_vilbrequin_chart_contracts
from frontend.components.moteur_thermique.pieces.vis_couvercle_cylindre.charts import build_chart_contracts as build_vis_chart_contracts
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


def test_graphes_attendus_pieces_restantes_sans_series_backend():
    cases = {
        "joint_deplaceur": build_joint_deplaceur_chart_contracts,
        "coussinet_arbre_piston": build_coussinet_chart_contracts,
        "roulement_aiguille_arbre": build_roulement_arbre_chart_contracts,
        "roulement_aiguille_arbre_vilebrequin": build_roulement_vilebrequin_chart_contracts,
        "vis_couvercle_cylindre": build_vis_chart_contracts,
    }

    for piece, builder in cases.items():
        charts = builder(global_report={"rapports_pieces": {piece: {"piece": piece}}})
        assert charts[0]["status"] == "missing_required"
        assert charts[0]["expected_quantities"]
        assert charts[0]["series"] == []

    assert "pv" in expected_quantities_for_piece("coussinet_arbre_piston")
    assert "l10" in expected_quantities_for_piece("roulement_aiguille_arbre")
    assert "charge_maneton" in expected_quantities_for_piece("roulement_aiguille_arbre_vilebrequin")
    assert "couple_serrage" in expected_quantities_for_piece("vis_couvercle_cylindre")


def test_roulement_arbre_ne_recupere_pas_graphes_roulement_vilebrequin():
    report = {
        "mechanical_graphs": {
            "graphiques": [
                {
                    "id": "roulement_aiguille_arbre_vilebrequin_charge_maneton",
                    "piece": "roulement_aiguille_arbre_vilebrequin",
                    "status": "computed",
                    "trace": {"producer": "backend"},
                    "series": [{"name": "backend", "points": [{"x": 1, "y": 2}]}],
                }
            ]
        }
    }

    arbre = build_roulement_arbre_chart_contracts(global_report=report)
    vilebrequin = build_roulement_vilebrequin_chart_contracts(global_report=report)

    assert arbre[0]["status"] == "missing_required"
    assert arbre[0]["series"] == []
    assert vilebrequin[0]["status"] == "computed"
    assert vilebrequin[0]["quantity_family"] == "charge_maneton"


def test_arbre_vilebrequin_et_vilbrequin_gardent_des_profils_graphiques_distincts():
    assert "interface_tourillon" in expected_quantities_for_piece("arbre_vilebrequin")
    assert "maneton" in expected_quantities_for_piece("vilbrequin")

    arbre = build_arbre_vilebrequin_chart_contracts(global_report={"rapports_pieces": {"arbre_vilebrequin": {"piece": "arbre_vilebrequin"}}})
    vilo = build_vilbrequin_chart_contracts(global_report={"rapports_pieces": {"vilbrequin": {"piece": "vilbrequin"}}})

    assert arbre[0]["render_profile"] == "arbre_vilebrequin"
    assert vilo[0]["render_profile"] == "vilebrequin"
