from __future__ import annotations

import json

from frontend.components.moteur_thermique.pieces.arbre_piston.mesh_3d import build_view_3d_contract
from frontend.components.batterie.pieces.pack_batterie.mesh_3d import build_view_3d_contract as build_pack_view_3d_contract


def test_mesh_3d_missing_required_sans_dimensions():
    view = build_view_3d_contract(data={"piece": "arbre_piston", "cao": {}})

    json.dumps(view, ensure_ascii=False)
    assert view["status"] == "missing_required"
    assert view["mesh_available"] is False
    assert view["warning"]


def test_mesh_3d_indicative_depuis_dimensions_backend():
    view = build_view_3d_contract(
        data={
            "piece": "arbre_piston",
            "cao": {
                "axe_x": {"x_debut_gauche_m": 0.0, "x_fin_teton_gauche_m": 0.02, "x_fin_teton_droit_m": 0.10},
                "fut_central": {"diametre_exterieur_m": 0.026},
            },
        }
    )

    assert view["status"] == "available"
    assert view["type"] == "view_3d_indicative"
    assert view["json_geometry"]["primitive"] == "shaft_stepped"
    assert view["json_geometry"]["sections"]
    assert view["schematic"] is True
    assert view["final_geometry"] is False
    assert view["solidworks_ready"] is False
    assert "pas STEP" in view["warning"]


def test_mesh_3d_reste_partiel_si_geometrie_incomplete():
    view = build_view_3d_contract(data={"piece": "arbre_piston", "cao": {"fut_central": {"diametre_exterieur_m": 0.026}}})

    assert view["status"] == "partial"
    assert view["json_geometry"]["sections"] == []
    assert view["missing_fields"]
    assert view["quality"] == "partial_schematic"


def test_mesh_3d_pack_batterie_utilise_enveloppe_sans_finaliser_cao():
    view = build_pack_view_3d_contract(
        data={
            "piece": "pack_batterie",
            "dimensions": {"longueur_mm": 900, "largeur_mm": 450, "hauteur_mm": 180},
        }
    )

    assert view["status"] == "available"
    assert view["json_geometry"]["primitive"] == "box_envelope"
    assert view["json_geometry"]["outline_2d"]["type"] == "rectangle_from_backend_dimensions"
    assert view["mesh_available"] is False
    assert view["final_geometry"] is False
