from __future__ import annotations

from frontend.ensemble.dashboard_model import build_dashboard_model, build_mechanical_model, build_power_chain_model


def test_dashboard_model_contient_entree_puissance_et_chaines():
    state = {
        "inputs": {"puissance_sortie": 100.0, "unite": "kW", "puissance_sortie_kw": 100.0, "status": "input"},
        "raw_report": {
            "frontend": {
                "fields": [
                    {"path": "synthese.moteur_electrique.puissance_sortie_w", "value": 100000.0, "status": "computed"},
                    {"path": "synthese.systeme.P_bus_dc_design_w", "value": 121000.0, "status": "computed"},
                ],
                "cao": {"step_export": False, "solidworks_ready": False},
            },
            "validation_chaine_100kw": {
                "ok": True,
                "score_chaine_100": 100.0,
                "valeurs": {"couple_moteur_thermique_nm": 1088.0},
            },
        },
    }

    dashboard = build_dashboard_model(state)
    assert dashboard["dashboard"]["design_input"]["value"] == 100.0
    assert build_power_chain_model(state)[0]["value"] == 100000.0
    assert build_mechanical_model(state)
    assert dashboard["dashboard"]["summary"]["cao_preconception"]["step_export"] is False
