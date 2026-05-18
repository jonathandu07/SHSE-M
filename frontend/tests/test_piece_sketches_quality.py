from __future__ import annotations

import json

import pytest

from frontend.components.moteur_thermique.pieces.arbre_piston.sketches_2d import build_sketch_contract, tracer_croquis


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
            "teton_gauche": {"diametre_m": 0.018},
            "fut_central": {"diametre_exterieur_m": 0.026},
            "teton_droit": {"diametre_m": 0.018},
        },
    }


def test_sketch_missing_required_si_cotes_principales_absentes():
    sketch = build_sketch_contract(data={"piece": "arbre_piston", "cao": {}})

    json.dumps(sketch, ensure_ascii=False)
    assert sketch["status"] == "missing_required"
    assert sketch["missing_fields"]
    assert sketch["geometry_json"]["segments"] == []


def test_sketch_available_si_cotes_principales_backend_presentes():
    sketch = build_sketch_contract(data=_piece_report())

    assert sketch["status"] == "available"
    assert sketch["geometry_json"]["segments"]
    assert sketch["solidworks_dimensions"]
    assert all(item["source"] == "backend" for item in sketch["solidworks_dimensions"])


def test_tracer_croquis_refuse_piece_non_cotee():
    with pytest.raises(ValueError):
        tracer_croquis(data={"piece": "arbre_piston", "cao": {}})
