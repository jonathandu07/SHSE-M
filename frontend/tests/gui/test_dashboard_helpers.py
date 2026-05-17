from frontend.main import _fuel_summary, _missing_requirements, PROJECT_NAME
from frontend.gui.dashboard import build_dashboard_ui_from_backend


def test_missing_requirements_reads_architecture_analysis():
    report = {
        "analyses_composants": {
            "architecture": {
                "inconnues": {
                    "impossibles": [
                        {"nom": "regime_tr_min", "raison": "RPM requis."},
                        {"nom": "pme_pa", "raison": "PME requise."},
                    ],
                    "partielles": [
                        {"nom": "gabarit (L/W)", "raison": "Packaging."},
                    ],
                }
            }
        }
    }

    items = _missing_requirements(report)

    assert [item["name"] for item in items[:3]] == ["RPM nominal", "PME", "gabarit L/W"]


def test_fuel_summary_reads_multifuel_backend_block():
    report = {
        "analyses_composants": {
            "moteur_thermique_bilan_carburant": {
                "mode": "multi_carburant_optimise_sur_pire_cas",
                "carburant_dimensionnant": "hydrogene",
                "carburant_optimal": "diesel",
            }
        }
    }

    summary = _fuel_summary(report)

    assert summary == {
        "mode": "multi_carburant_optimise_sur_pire_cas",
        "worst": "hydrogene",
        "best": "diesel",
    }


def test_project_name_is_sthome():
    assert PROJECT_NAME == "STHOME"


def test_dashboard_reads_100kw_chain_validation_without_calculating():
    ui = build_dashboard_ui_from_backend(
        {
            "validation_chaine_100kw": {
                "ok": False,
                "score_chaine_100": 42.0,
                "points_bloquants": [{"name": "rpm_moteur_connu_ou_candidat"}],
            }
        }
    )

    summary = ui["dashboard"]["summary"]["chain_validation"]
    assert summary["available"] is True
    assert summary["ok"] is False
    assert summary["score_chaine_100"] == 42.0
    assert summary["main_blocking_point"]["name"] == "rpm_moteur_connu_ou_candidat"


def test_dashboard_expose_cartes_backend_modernes():
    ui = build_dashboard_ui_from_backend(
        {
            "frontend": {
                "fields": [
                    {
                        "path": "synthese.moteur_electrique.puissance_sortie_w",
                        "value": 100000.0,
                        "unit": "W",
                        "status": "computed",
                    },
                    {
                        "path": "synthese.systeme.P_bus_dc_design_w",
                        "value": 120967.7,
                        "unit": "W",
                        "status": "computed",
                    },
                ],
                "cao": {
                    "mode": "3d_indicative",
                    "available": False,
                    "solidworks_ready": False,
                    "step_export": False,
                    "sketches_available": True,
                    "views_3d_available": True,
                    "stress_graphs_available": True,
                    "drawing_data_available": True,
                },
            },
            "validation_chaine_100kw": {
                "ok": True,
                "score_chaine_100": 100.0,
                "valeurs": {
                    "puissance_alternateur_electrique_w": 266000.0,
                    "puissance_moteur_thermique_arbre_w": 342000.0,
                    "rpm_moteur_thermique": 3000.0,
                    "couple_moteur_thermique_nm": 1088.0,
                },
                "livrables": {"mechanical_presizing_ok": True},
                "checks": [
                    {"name": "boite_reliable", "ok": True},
                    {"name": "couple_moteur_thermique_calculable", "ok": True},
                ],
            },
            "mechanical_graphs": {
                "graphs_available": 6,
                "context": {"materiaux_autorises": ["acier_42crmo4_qt"]},
            },
            "diagnostic": {
                "resume": {"statut": "partiel", "score_diagnostic_100": 80, "nb_causes_racines": 1, "nb_symptomes": 4},
                "causes_racines": [{"id": "cao_non_fermee", "raison": "Montage détaillé absent"}],
            },
        }
    )

    dash = ui["dashboard"]
    assert dash["power_chain"][0]["value"] == 100000.0
    assert dash["mechanical_closure"][1]["value"] == "OUI"
    assert dash["cao_preconception"][1]["value"] == "OUI"
    assert dash["cao_preconception"][5]["value"] == "NON"
    assert dash["cao_preconception"][6]["value"] == "NON"
    assert dash["diagnostic_causal"]["root_causes_count"] == 1
