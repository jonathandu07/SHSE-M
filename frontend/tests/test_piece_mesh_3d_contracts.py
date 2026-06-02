from __future__ import annotations

import json

from frontend.components.moteur_thermique.pieces.arbre_piston.mesh_3d import build_view_3d_contract
from frontend.components.moteur_thermique.pieces.arbre_vilebrequin.mesh_3d import build_view_3d_contract as build_arbre_vilebrequin_view_3d_contract
from frontend.components.moteur_thermique.pieces.coussinet_arbre_piston.mesh_3d import build_view_3d_contract as build_coussinet_view_3d_contract
from frontend.components.moteur_thermique.pieces.joint_deplaceur.mesh_3d import build_view_3d_contract as build_joint_deplaceur_view_3d_contract
from frontend.components.moteur_thermique.pieces.joint_piston.mesh_3d import build_view_3d_contract as build_joint_piston_view_3d_contract
from frontend.components.moteur_thermique.pieces.piston.mesh_3d import build_view_3d_contract as build_piston_view_3d_contract
from frontend.components.moteur_thermique.pieces.roulement_aiguille_arbre.mesh_3d import build_view_3d_contract as build_roulement_arbre_view_3d_contract
from frontend.components.moteur_thermique.pieces.roulement_aiguille_arbre_vilebrequin.mesh_3d import build_view_3d_contract as build_roulement_vilebrequin_view_3d_contract
from frontend.components.moteur_thermique.pieces.vis_couvercle_cylindre.mesh_3d import build_view_3d_contract as build_vis_view_3d_contract
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
    assert "preparation a la modelisation" in view["warning"]


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


def test_mesh_piston_specialise_reste_schematique_et_non_final():
    view = build_piston_view_3d_contract(
        data={
            "piece": "piston",
            "dimensions": {
                "diametre_exterieur_m": 0.08,
                "hauteur_piston_m": 0.055,
                "largeur_gorge_segment_m": 0.002,
            },
        }
    )

    features = {item["type"] for item in view["json_geometry"]["features"]}
    assert view["status"] == "available"
    assert view["json_geometry"]["primitive"] == "piston_simplifie"
    assert "ring_groove" in features
    assert view["schematic"] is True
    assert view["final_geometry"] is False
    assert view["solidworks_ready"] is False


def test_mesh_vilebrequin_alias_maneton_tourillon_sans_renommage():
    view = build_arbre_vilebrequin_view_3d_contract(
        data={
            "piece": "arbre_vilebrequin",
            "geometrie": {
                "longueur_totale_m": 0.42,
                "diametre_journal_principal_m": 0.048,
                "diametre_maneton_m": 0.042,
                "rayon_manivelle_m": 0.035,
            },
        }
    )

    features = {item["type"] for item in view["json_geometry"]["features"]}
    assert view["json_geometry"]["primitive"] == "crankshaft_interface_shaft_schematic"
    assert view["json_geometry"]["render_profile"] == "arbre_vilebrequin"
    assert "crankshaft_interface_journal" in features
    assert "interface_shaft_diameter" in features
    assert "crank_offset_reference" in features
    assert view["schematic"] is True
    assert view["final_geometry"] is False


def test_mesh_joint_piston_tore_schematique_si_section_presente():
    view = build_joint_piston_view_3d_contract(
        data={
            "piece": "joint_piston",
            "geometrie": {
                "diametre_interieur_joint_m": 0.078,
                "epaisseur_joint_m": 0.003,
                "squeeze": 0.12,
            },
        }
    )

    features = {item["type"] for item in view["json_geometry"]["features"]}
    assert view["status"] == "available"
    assert view["json_geometry"]["primitive"] == "seal_ring_envelope"
    assert {"seal_inner_diameter", "seal_section", "squeeze"} <= features
    assert view["schematic"] is True
    assert view["final_geometry"] is False


def test_mesh_joint_deplaceur_coussinet_roulements_vis_profils_dedies():
    joint = build_joint_deplaceur_view_3d_contract(
        data={"piece": "joint_deplaceur", "geometrie": {"diametre_interieur_joint_m": 0.072, "section_joint_m": 0.003}}
    )
    coussinet = build_coussinet_view_3d_contract(
        data={"piece": "coussinet_arbre_piston", "geometrie": {"diametre_interieur_m": 0.022, "diametre_exterieur_m": 0.032, "longueur_m": 0.028}}
    )
    roulement_arbre = build_roulement_arbre_view_3d_contract(
        data={"piece": "roulement_aiguille_arbre", "dimensions": {"diametre_interieur_m": 0.022, "diametre_exterieur_m": 0.030, "largeur_m": 0.018, "nombre_aiguilles": 18}}
    )
    roulement_vilebrequin = build_roulement_vilebrequin_view_3d_contract(
        data={"piece": "roulement_aiguille_arbre_vilebrequin", "dimensions": {"diametre_maneton_m": 0.042, "diametre_exterieur_m": 0.055, "largeur_m": 0.024, "nombre_aiguilles": 22}}
    )
    vis = build_vis_view_3d_contract(
        data={"piece": "vis_couvercle_cylindre", "geometrie": {"diametre_nominal_m": 0.010, "longueur_vis_min_m": 0.055, "pas_vis_m": 0.0015}}
    )

    assert joint["json_geometry"]["primitive"] == "displacer_seal_ring_envelope"
    assert coussinet["json_geometry"]["primitive"] == "plain_bearing_bushing_envelope"
    assert roulement_arbre["json_geometry"]["primitive"] == "needle_bearing_envelope"
    assert roulement_vilebrequin["json_geometry"]["primitive"] == "needle_bearing_envelope"
    assert vis["json_geometry"]["primitive"] == "screw_thread_schematic"
    for view in (joint, coussinet, roulement_arbre, roulement_vilebrequin, vis):
        assert view["schematic"] is True
        assert view["final_geometry"] is False
        assert view["solidworks_ready"] is False
