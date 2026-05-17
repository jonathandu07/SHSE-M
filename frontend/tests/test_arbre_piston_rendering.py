from __future__ import annotations

import json

from frontend.components.moteur_thermique.pieces.arbre_piston.arbre_piston import visualiser_piece


def _piece_report() -> dict:
    return {
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


def test_arbre_piston_ne_lance_pas_run_100kw_si_rapport_fourni(monkeypatch):
    def fail_bridge():
        raise AssertionError("run_100kw ne doit pas etre appele avec data fourni")

    monkeypatch.setattr("frontend.main.get_backend_bridge", fail_bridge)

    contract = visualiser_piece(data=_piece_report(), global_report={"rapports_pieces": {"arbre_piston": _piece_report()}})

    assert contract["id"] == "arbre_piston"
    assert contract["sketches_2d"][0]["status"] == "available"
    assert contract["views_3d"][0]["status"] == "available"


def test_arbre_piston_contrat_missing_required_si_cotes_absentes():
    contract = visualiser_piece(data={"piece": "arbre_piston", "cao": {}}, global_report={})

    json.dumps(contract, ensure_ascii=False)
    sketch = contract["sketches_2d"][0]
    view = contract["views_3d"][0]
    assert sketch["status"] == "missing_required"
    assert view["status"] == "missing_required"
    assert sketch["missing_fields"]
    assert contract["solidworks_data"]["step_export"] is False

