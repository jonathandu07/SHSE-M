from __future__ import annotations

import json

import pytest

from frontend.components.moteur_thermique.pieces.arbre_piston.sketches_2d import build_sketch_contract, tracer_croquis
from frontend.components.moteur_thermique.pieces.bielle.sketches_2d import build_sketch_contract as build_bielle_sketch_contract
from frontend.components.moteur_thermique.pieces.couvercle_cylindre.sketches_2d import build_sketch_contract as build_couvercle_sketch_contract
from frontend.components.moteur_thermique.pieces.cylindre.sketches_2d import build_sketch_contract as build_cylindre_sketch_contract
from frontend.components.moteur_thermique.pieces.deplaceur.sketches_2d import build_sketch_contract as build_deplaceur_sketch_contract
from frontend.components.moteur_thermique.pieces.joint_piston.sketches_2d import build_sketch_contract as build_joint_piston_sketch_contract
from frontend.components.moteur_thermique.pieces.piston.sketches_2d import build_sketch_contract as build_piston_sketch_contract
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


def _feature_types(sketch: dict) -> set[str]:
    return {item.get("type") for item in sketch["geometry_json"].get("features", [])}


def test_piston_croquis_specialise_rainures_uniquement_si_donnees_backend():
    base = {
        "piece": "piston",
        "dimensions": {"diametre_exterieur_m": 0.08, "hauteur_piston_m": 0.055},
    }
    sketch = build_piston_sketch_contract(data=base)

    assert sketch["status"] == "available"
    assert sketch["geometry_json"]["sketch_style"] == "piston_longitudinal_section"
    assert "piston_outer_diameter" in _feature_types(sketch)
    assert "ring_groove" not in _feature_types(sketch)
    assert sketch["geometry_json"]["final_geometry"] is False

    with_groove = build_piston_sketch_contract(
        data={
            **base,
            "rainures": {"largeur_gorge_m": 0.002, "profondeur_gorge_m": 0.001},
        }
    )

    assert "ring_groove" in _feature_types(with_groove)


def test_cylindre_croquis_specialise_coupe_longitudinale():
    sketch = build_cylindre_sketch_contract(
        data={
            "piece": "cylindre",
            "geometrie": {
                "longueur_utile_m": 0.16,
                "diametre_interieur_m": 0.08,
                "diametre_exterieur_m": 0.095,
                "epaisseur_paroi_m": 0.0075,
                "diametre_cercle_percage_m": 0.12,
            },
        }
    )

    features = _feature_types(sketch)
    assert sketch["status"] == "available"
    assert sketch["geometry_json"]["sketch_style"] == "cylinder_longitudinal_section"
    assert {"cylinder_bore", "cylinder_outer_diameter", "cylinder_wall_thickness", "bolt_holes"} <= features


def test_bielle_croquis_marque_tetes_et_entraxe_sans_finaliser():
    sketch = build_bielle_sketch_contract(
        data={
            "piece": "bielle",
            "geometrie": {
                "longueur_bielle_m": 0.18,
                "diametre_axe_piston_m": 0.022,
                "diametre_maneton_m": 0.036,
                "section_fut_m2": 0.00018,
            },
        }
    )

    features = _feature_types(sketch)
    assert sketch["status"] == "available"
    assert sketch["geometry_json"]["sketch_style"] == "connecting_rod_centerline_schematic"
    assert {"small_end", "big_end", "center_distance", "beam_section"} <= features
    assert sketch["geometry_json"]["schematic"] is True
    assert sketch["geometry_json"]["final_geometry"] is False


def test_joint_deplaceur_couvercle_restant_partiels_si_cotes_manquantes():
    joint = build_joint_piston_sketch_contract(data={"piece": "joint_piston", "geometrie": {"diametre_interieur_joint_m": 0.078}})
    deplaceur = build_deplaceur_sketch_contract(data={"piece": "deplaceur", "geometrie": {"diametre_exterieur_m": 0.075}})
    couvercle = build_couvercle_sketch_contract(data={"piece": "couvercle_cylindre", "geometrie": {"diametre_bride_externe_m": 0.13}})

    assert joint["status"] == "partial"
    assert deplaceur["status"] == "partial"
    assert couvercle["status"] == "partial"
    assert joint["missing_fields"]
    assert deplaceur["missing_fields"]
    assert couvercle["missing_fields"]
