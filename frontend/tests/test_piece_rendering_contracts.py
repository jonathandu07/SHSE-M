from __future__ import annotations

import json

from frontend.ensemble.render_contract import build_piece_render_contract
from frontend.gui.technical_visualization import build_technical_visualization_payload
from frontend.main import get_technical_visualization_report


def test_render_contract_generique_ne_declare_pas_step():
    report = {"rapports_pieces": {"piston": {"piece": "piston", "cao": {"diametre_exterieur_m": 0.08}}}}

    contract = build_piece_render_contract("piston", report)

    json.dumps(contract, ensure_ascii=False)
    assert contract["solidworks_data"]["step_export"] is False
    assert contract["solidworks_data"]["solidworks_ready"] is False
    assert contract["solidworks_data"]["dimensions_to_copy"][0]["source"] == "backend"


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

