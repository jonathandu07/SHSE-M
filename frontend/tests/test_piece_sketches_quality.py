from __future__ import annotations

import json

import pytest

from frontend.components.moteur_thermique.pieces.arbre_piston.sketches_2d import build_sketch_contract, tracer_croquis
from frontend.components.batterie.pieces.pack_batterie.sketches_2d import build_sketch_contract as build_pack_sketch_contract
from frontend.components.batterie.pieces.pack_batterie.sketches_2d import tracer_croquis as tracer_pack_croquis


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


def test_croquis_pack_batterie_trace_enveloppe_cotee_non_finale():
    sketch = build_pack_sketch_contract(
        data={
            "piece": "pack_batterie",
            "dimensions": {"longueur_mm": 900, "largeur_mm": 450, "hauteur_mm": 180},
        }
    )

    assert sketch["status"] == "available"
    assert sketch["geometry_json"]["outline_2d"]["width_mm"] == 900
    assert sketch["geometry_json"]["outline_2d"]["height_mm"] == 450
    fig = tracer_pack_croquis(
        data={
            "piece": "pack_batterie",
            "dimensions": {"longueur_mm": 900, "largeur_mm": 450, "hauteur_mm": 180},
        }
    )
    fig.clear()
