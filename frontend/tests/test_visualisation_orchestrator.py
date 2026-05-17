from __future__ import annotations

import json

from frontend.ensemble.visualisation_orchestrator import (
    construire_tableau_pages_visualisation,
    construire_visualisation_piece,
    lister_visualisations_disponibles,
)


def _report_arbre_piston() -> dict:
    return {
        "rapports_pieces": {
            "arbre_piston": {
                "piece": "arbre_piston",
                "cao": {
                    "axe_x": {
                        "x_debut_gauche_m": 0.0,
                        "x_fin_teton_gauche_m": 0.02,
                        "x_fin_fut_central_m": 0.08,
                        "x_fin_teton_droit_m": 0.10,
                    },
                    "teton_gauche": {"diametre_m": 0.018, "longueur_m": 0.02},
                    "fut_central": {"diametre_exterieur_m": 0.026, "diametre_interieur_m": 0.0, "longueur_m": 0.06},
                    "teton_droit": {"diametre_m": 0.018, "longueur_m": 0.02},
                },
            }
        },
        "cao_dossier": {
            "croquis_2d": [{"id": "arbre_piston_backend", "piece": "arbre_piston", "statut": "available"}],
            "vues_3d": [{"id": "arbre_piston_backend_3d", "piece": "arbre_piston", "status": "available", "dimensions": {"diametre_m": 0.026}}],
        },
        "mechanical_graphs": {
            "graphiques": [
                {
                    "id": "arbre_piston_torsion",
                    "piece": "arbre_piston",
                    "status": "available",
                    "series": [{"name": "backend", "points": [{"x": 20, "y": 100}]}],
                }
            ]
        },
    }


def test_visualisation_orchestrator_liste_les_pieces_disponibles():
    inventory = lister_visualisations_disponibles(_report_arbre_piston())

    names = {row["piece"] for row in inventory["pieces"]}
    assert "arbre_piston" in names
    assert inventory["summary"]["step_export"] is False
    assert inventory["summary"]["solidworks_ready"] is False


def test_visualisation_orchestrator_construit_arbre_piston_json_serializable():
    contract = construire_visualisation_piece("arbre_piston", _report_arbre_piston())

    json.dumps(contract, ensure_ascii=False)
    assert contract["id"] == "arbre_piston"
    assert contract["solidworks_data"]["step_export"] is False
    assert contract["solidworks_data"]["solidworks_ready"] is False
    assert contract["sketches_2d"]
    assert contract["views_3d"][0]["type"] == "view_3d_indicative"
    assert contract["views_3d"][0]["warning"]
    assert contract["charts"][0]["series"][0]["points"] == [{"x": 20, "y": 100}]


def test_tableau_pages_visualisation_expose_solidworks_passif():
    table = construire_tableau_pages_visualisation(_report_arbre_piston())

    assert "moteur_thermique" in table["pieces_by_family"]
    assert table["solidworks"]["step_export"] is False
    assert table["solidworks"]["solidworks_ready"] is False

