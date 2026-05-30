from __future__ import annotations

from frontend.ensemble.dashboard_model import build_dashboard_model, build_mechanical_model, build_power_chain_model
from frontend.ensemble.graph_rendering import build_chart_figure
from frontend.ensemble.graphs_adapter import collect_backend_charts


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


def test_dashboard_respecte_statuts_contractuels_des_champs():
    state = {
        "raw_report": {
            "frontend": {
                "fields": [
                    {"path": "synthese.moteur_electrique.puissance_sortie_w", "value": 100000.0, "status": "candidate_from_cdc"},
                    {"path": "synthese.systeme.P_bus_dc_design_w", "value": 121000.0, "status": "validated_by_optimization", "trace": {"validation": "ok"}},
                ],
            }
        }
    }

    chain = build_power_chain_model(state)

    assert chain[0]["status"] == "candidate_from_cdc"
    assert chain[0]["confidence"] == "untraced_report_value"
    assert chain[1]["status"] == "validated_by_optimization"
    assert chain[1]["trace_present"] is True


def test_graphes_sans_trace_sont_signales_partiels():
    report = {
        "mechanical_graphs": {
            "graphiques": [
                {"id": "g1", "status": "computed", "series": [{"points": [[0, 0], [1, 1]]}]}
            ]
        }
    }

    graphs = collect_backend_charts(report)

    assert graphs["status"] == "partial"
    assert graphs["charts"][0]["status"] == "partial"
    assert graphs["warnings"]
    try:
        build_chart_figure(graphs["charts"][0])
    except ValueError as exc:
        assert "statut backend partial" in str(exc)
    else:
        raise AssertionError("Un graphe partiel ne doit pas etre trace comme final.")
