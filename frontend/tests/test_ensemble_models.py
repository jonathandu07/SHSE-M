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
        "frontend_inputs": {"puissance_sortie": 100.0, "unite": "kW", "puissance_sortie_kw": 100.0, "puissance_sortie_w": 100000.0, "status": "input"},
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
    assert dashboard["dashboard"]["design_input"]["value"] == 100.0
    assert dashboard["dashboard"]["cards"]["design_input"]["palette"]["background"]
    assert cao["summary"]["step_export"] is False
    assert visualisations["solidworks"]["step_export"] is False
    assert piece["step_export"] is False


def test_cao_model_expose_dossiers_definition_pieces_sans_step():
    report = {
        "rapports_pieces": {
            "joint_deplaceur": {
                "piece": "joint_deplaceur",
                "dossier_definition_piece": {
                    "statut": "ready_for_modeling",
                    "solidworks_ready": True,
                    "step_generation": True,
                    "final_geometry": True,
                    "schema_only": True,
                    "cotes_connues": {"diametre_interieur_m": 0.045},
                    "cotes_manquantes": {"section_joint_m": {"raison": "absente"}},
                    "interfaces_assemblage": [{"piece_b": "deplaceur"}],
                    "tolerances": [{"nom": "squeeze"}],
                    "inconnues_bloquantes": [{"nom": "gorge_joint"}],
                },
            }
        }
    }

    cao = build_cao_model({"raw_report": report})
    dossiers = cao["piece_definition_dossiers"]

    assert len(dossiers) == 1
    assert dossiers[0]["piece"] == "joint_deplaceur"
    assert dossiers[0]["statut"] == "ready_for_modeling"
    assert dossiers[0]["solidworks_ready"] is False
    assert dossiers[0]["step_generation"] is False
    assert dossiers[0]["step_export"] is False
    assert dossiers[0]["final_geometry"] is False
    assert dossiers[0]["counts"]["cotes_connues"] == 1
    assert dossiers[0]["counts"]["cotes_manquantes"] == 1
    assert dossiers[0]["counts"]["interfaces"] == 1
    assert dossiers[0]["counts"]["tolerances"] == 1
    assert dossiers[0]["counts"]["inconnues_bloquantes"] == 1
