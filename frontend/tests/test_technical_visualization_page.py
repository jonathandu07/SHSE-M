from __future__ import annotations

import json

from frontend.gui.technical_visualization import build_technical_visualization_payload


def test_payload_visualisation_expose_couverture_actions_et_solidworks_passif():
    payload = build_technical_visualization_payload(
        {
            "rapports_pieces": {"arbre_piston": {"piece": "arbre_piston"}},
            "cao_dossier": {"croquis_2d": [{"id": "c1", "piece": "arbre_piston"}]},
            "mechanical_graphs": {"graphiques": [{"id": "g1", "series": [{"name": "backend", "points": [{"x": 1, "y": 2}]}]}]},
        }
    )

    json.dumps(payload, ensure_ascii=False)
    assert payload["solidworks"]["step_export"] is False
    assert payload["solidworks"]["solidworks_ready"] is False
    assert payload["coverage"]["summary"]["frontend_pieces"] >= 1
    assert payload["actions"]
    assert payload["table"]["graphs_summary"]["charts"][0]["series"][0]["points"] == [{"x": 1, "y": 2}]


def test_payload_visualisation_reste_robuste_sans_sections_backend():
    payload = build_technical_visualization_payload({})

    assert payload["title"] == "VISUALISATION TECHNIQUE"
    assert payload["solidworks"]["step_export"] is False
    assert payload["coverage"]["summary"]["backend_pieces"] >= 0
