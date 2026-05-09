from frontend.main import _fuel_summary, _missing_requirements, PROJECT_NAME


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
