from __future__ import annotations

import json
from pathlib import Path

from frontend.ensemble.render_contract import build_piece_render_contract
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
        assert contract["sketches_2d"][0]["status"] == "missing_required"
        assert contract["views_3d"][0]["final_geometry"] is False
        assert contract["missing_fields"]
