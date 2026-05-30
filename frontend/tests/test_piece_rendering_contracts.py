from __future__ import annotations

import json
from pathlib import Path

from frontend.ensemble.render_contract import build_piece_render_contract
from frontend.ensemble.piece_rendering import build_piece_visualization_contract
from frontend.gui.technical_visualization import build_technical_visualization_payload
from frontend.main import get_technical_visualization_report


def test_render_contract_generique_ne_declare_pas_step():
    report = {"rapports_pieces": {"piston": {"piece": "piston", "cao": {"diametre_exterieur_m": 0.08}}}}

    contract = build_piece_render_contract("piston", report)

    json.dumps(contract, ensure_ascii=False)
    assert contract["step_export"] is False
    assert contract["solidworks_ready"] is False
    assert contract["solidworks_data"]["step_export"] is False
    assert contract["solidworks_data"]["solidworks_ready"] is False
    assert contract["solidworks_data"]["dimensions_to_copy"][0]["source"] == "backend"
    dossier = contract["dossier_definition_solidworks"]
    assert dossier["step_generation"] is False
    assert dossier["schema_only"] is True
    assert dossier["final_geometry"] is False
    assert dossier["solidworks_ready"] is False


def test_render_contract_remonte_toutes_categories_inconnues():
    report = {
        "rapports_pieces": {
            "piston": {
                "piece": "piston",
                "inconnues": {
                    "bloquantes": [{"nom": "alesage_m", "raison": "manquant"}],
                    "thermique": [{"nom": "temperature_max_c", "raison": "modele absent"}],
                },
            }
        }
    }

    contract = build_piece_render_contract("piston", report)
    names = {item.get("nom") or item.get("name") for item in contract["missing_fields"]}

    assert "alesage_m" in names
    assert "temperature_max_c" in names
    assert contract["solidworks_ready"] is False


def test_frontend_main_expose_tableau_visualisation():
    table = get_technical_visualization_report({"rapports_pieces": {"arbre_piston": {"piece": "arbre_piston"}}})

    assert table["title"] == "Visualisation technique"
    assert table["solidworks"]["step_export"] is False


def test_gui_payload_visualisation_technique_robuste_sections_absentes():
    payload = build_technical_visualization_payload({})

    assert payload["title"] == "VISUALISATION TECHNIQUE"
    assert payload["solidworks"]["step_export"] is False
    assert "components" in payload
    assert "pieces_by_family" in payload


def test_toutes_les_pieces_frontend_exposent_modules_de_rendu_standards():
    required = {"data_adapter.py", "render_contract.py", "charts.py", "mesh_3d.py", "sketches_2d.py", "views_3d.py"}
    pieces = [path for path in Path("frontend/components").glob("*/pieces/*") if path.is_dir()]

    assert pieces
    for piece_dir in pieces:
        expected = required | {f"{piece_dir.name}.py"}
        missing = [name for name in expected if not (piece_dir / name).is_file()]
        assert not missing, f"{piece_dir}: modules manquants {missing}"


def test_pieces_moteur_thermique_prioritaires_construisent_contrat_passif():
    from frontend.ensemble.visualisation_orchestrator import construire_visualisation_piece

    priority = [
        "piston",
        "cylindre",
        "bielle",
        "arbre_piston",
        "arbre_vilbrequin",
        "arbre_vilebrequin",
        "vilbrequin",
        "joint_piston",
        "deplaceur",
        "couvercle_cylindre",
        "joint_deplaceur",
        "coussinet_arbre_piston",
        "roulement_aiguille_arbre",
        "roulement_aiguille_arbre_vilebrequin",
        "vis_couvercle_cylindre",
    ]
    report = {
        "rapports_pieces": {
            name: {"piece": name, "inconnues_cao": [{"nom": "cotes", "raison": "donnees backend absentes"}]}
            for name in priority
        }
    }

    for name in priority:
        contract = construire_visualisation_piece(name, report)
        json.dumps(contract, ensure_ascii=False)
        assert contract["id"] == name
        assert contract["step_export"] is False
        assert contract["solidworks_ready"] is False
        if contract["sketches_2d"]:
            assert contract["sketches_2d"][0]["status"] == "missing_required"
        else:
            assert name == "arbre_vilbrequin"
        if contract["views_3d"]:
            assert contract["views_3d"][0]["final_geometry"] is False
        else:
            assert name == "arbre_vilbrequin"
        assert contract["missing_fields"]


def test_dossier_definition_solidworks_reste_un_dossier_de_modelisation():
    report = {
        "rapports_pieces": {
            "piston": {
                "piece": "piston",
                "dimensions": {"diametre_exterieur_m": 0.08},
                "inconnues_cao": [{"nom": "tolerance_jeu_radial", "raison": "norme ou fabrication non fournie"}],
            }
        }
    }

    contract = build_piece_render_contract("piston", report)
    dossier = contract["dossier_definition_solidworks"]

    assert dossier["statut"] == "partial"
    assert dossier["step_generation"] is False
    assert dossier["solidworks_ready"] is False
    assert dossier["schema_only"] is True
    assert dossier["final_geometry"] is False
    assert "dimensions.diametre_exterieur_m" in dossier["cotes_connues"]
    assert "tolerance_jeu_radial" in dossier["cotes_manquantes"]
    assert "step_export" in contract
    assert contract["step_export"] is False


def test_ready_for_manual_modeling_exige_donnees_minimales_backend():
    no_dimensions = {
        "piece": "piston",
        "dossier_definition_solidworks": {"statut": "ready_for_manual_modeling"},
        "tolerances": {"jeu_radial": {"valeur": 0.0001, "unite": "m"}},
        "materiau": "acier",
    }
    dims_without_tolerances = {
        "piece": "piston",
        "dimensions": {"diametre_exterieur_m": 0.08, "hauteur_piston_m": 0.05},
        "dossier_definition_solidworks": {"statut": "ready_for_manual_modeling"},
        "materiau": "acier",
    }
    complete_definition = {
        **dims_without_tolerances,
        "tolerances": {"jeu_radial": {"valeur": 0.0001, "unite": "m"}},
    }

    assert build_piece_render_contract("piston", {"rapports_pieces": {"piston": no_dimensions}})["dossier_definition_solidworks"]["statut"] == "blocked"
    assert build_piece_render_contract("piston", {"rapports_pieces": {"piston": dims_without_tolerances}})["dossier_definition_solidworks"]["statut"] == "partial"
    assert build_piece_render_contract("piston", {"rapports_pieces": {"piston": complete_definition}})["dossier_definition_solidworks"]["statut"] == "ready_for_manual_modeling"


def test_piece_sans_rdm_reste_non_validee_et_interfaces_partielles():
    report = {
        "rapports_pieces": {
            "coussinet_arbre_piston": {
                "piece": "coussinet_arbre_piston",
                "dimensions": {"diametre_interieur_m": 0.022, "longueur_m": 0.028},
                "interfaces_assemblage": [
                    {"piece_a": "coussinet_arbre_piston", "piece_b": "arbre_piston", "type_liaison": "palier_lisse", "statut": "partial"}
                ],
                "materiau": "bronze_fourni_backend",
            }
        }
    }

    contract = build_piece_render_contract("coussinet_arbre_piston", report)
    dossier = contract["dossier_definition_solidworks"]

    assert dossier["statut"] == "partial"
    assert dossier["statut_validation"] == "not_validated"
    assert contract["interfaces_assemblage"][0]["statut"] == "partial"
    assert dossier["interfaces"][0]["type_liaison"] == "palier_lisse"


def test_dossier_definition_remonte_features_et_limites_backend_sans_finaliser():
    contract = build_piece_visualization_contract(
        "vis_couvercle_cylindre",
        data={
            "piece": "vis_couvercle_cylindre",
            "geometrie": {"diametre_nominal_m": 0.010, "longueur_vis_min_m": 0.055},
            "limites_usage": {"traction_max_n": 9000},
        },
    )
    dossier = contract["dossier_definition_solidworks"]
    feature_types = {item.get("type") for item in dossier["features_a_modeliser"]}

    assert "screw_shank" in feature_types
    assert dossier["limites_usage"][0]["nom"] == "traction_max_n"
    assert dossier["final_geometry"] is False
    assert dossier["solidworks_ready"] is False
