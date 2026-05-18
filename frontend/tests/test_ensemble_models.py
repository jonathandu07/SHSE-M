from __future__ import annotations

import json

from frontend.ensemble.screen_models import build_cao_model, build_dashboard_model, build_piece_render_model, build_visualisation_model


def _report() -> dict:
    return {
        "frontend": {
            "fields": [
                {"path": "synthese.moteur_electrique.puissance_sortie_w", "value": 100000.0, "status": "computed"},
                {"path": "synthese.systeme.P_bus_dc_design_w", "value": 120000.0, "status": "computed"},
            ],
            "cao": {"sketches_available": True, "views_3d_available": True, "step_export": False, "solidworks_ready": False},
        },
        "validation_chaine_100kw": {"ok": True, "score_chaine_100": 100.0, "valeurs": {"couple_moteur_thermique_nm": 1088.0}},
        "rapports_pieces": {"arbre_piston": {"piece": "arbre_piston", "cao": {"axe_x": {"x0_m": 0.0, "x1_m": 0.1}, "fut": {"diametre_m": 0.02}}}},
    }


def test_ensemble_construit_modeles_json_serializable():
    state = {"raw_report": _report()}

    dashboard = build_dashboard_model(state)
    cao = build_cao_model(state)
    visualisations = build_visualisation_model(state)
    piece = build_piece_render_model("arbre_piston", state)

    json.dumps({"dashboard": dashboard, "cao": cao, "visualisations": visualisations, "piece": piece}, ensure_ascii=False)
    assert dashboard["dashboard"]["power_chain"][0]["value"] == 100000.0
    assert cao["summary"]["step_export"] is False
    assert visualisations["solidworks"]["step_export"] is False
    assert piece["step_export"] is False
