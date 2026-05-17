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
