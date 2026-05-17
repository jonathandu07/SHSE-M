import math

import pytest

from backend.ensemble.resolution_inconnues import (
    CahierDesChargesSTHOME,
    appliquer_resolution_inconnues,
    resoudre_inconnues_systeme,
    tracer_resolution_inconnues,
)


def test_donnee_calculable_est_completee_et_tracee():
    report = resoudre_inconnues_systeme(
        {
            "puissance_moteur_requise_W": 100_000.0,
            "rpm_moteur_nominal": 3000.0,
        },
        {},
        CahierDesChargesSTHOME(autoriser_choix_materiau=False),
    )

    payload = report.payload_resolu
    assert payload["omega_moteur_rad_s"] == pytest.approx(2.0 * math.pi * 3000.0 / 60.0)
    assert payload["couple_moteur_nm"] == pytest.approx(100_000.0 / payload["omega_moteur_rad_s"])

    traces = {h.champ for h in report.hypotheses}
    assert "omega_moteur_rad_s" in traces
    assert "couple_moteur_nm" in traces
    assert set(report.donnees_auto_completees).issubset(traces)


def test_donnee_impossible_reste_classee():
    report = resoudre_inconnues_systeme(
        {"puissance_moteur_requise_W": 50_000.0},
        {},
        CahierDesChargesSTHOME(tension_bus_dc_v=None, autoriser_choix_materiau=False),
    )

    unresolved = report.inconnues["restantes_physiques"]
    assert any(item["champ"] == "cylindree_totale_m3" for item in unresolved)
    assert "cylindree_totale_m3" not in report.payload_resolu


def test_donnee_optimisable_est_resolue_avec_justification():
    report = resoudre_inconnues_systeme(
        {
            "puissance_moteur_requise_W": 60_000.0,
            "rpm_moteur_nominal": 3000.0,
            "pme_pa": 900_000.0,
        },
        {},
            CahierDesChargesSTHOME(
                autoriser_choix_materiau=False,
                vitesse_piston_max_ms=14.0,
                nombres_cylindres_autorises=(2, 3, 4, 6),
                alesage_min_m=0.04,
                alesage_max_m=0.18,
                course_min_m=0.04,
                course_max_m=0.22,
                ratio_course_alesage_min=0.75,
                ratio_course_alesage_max=1.35,
            ),
        )

    payload = report.payload_resolu
    assert payload["nombre_cylindres"] in {2, 3, 4, 6}
    assert 0.04 <= payload["alesage_m"] <= 0.18
    assert 0.04 <= payload["course_m"] <= 0.22

    traces = [h for h in report.hypotheses if h.champ in {"alesage_m", "course_m", "nombre_cylindres"}]
    assert traces
    assert all(h.type_resolution == "candidate_from_cdc" for h in traces)
    assert all(h.justification for h in traces)
    assert all("domaine" in h.validation for h in traces)


def test_application_et_trace_json_safe():
    report = resoudre_inconnues_systeme(
        {"puissance_traction_kw": 80.0},
        {},
        CahierDesChargesSTHOME(autoriser_choix_materiau=False),
    )

    applied = appliquer_resolution_inconnues({}, report)
    assert applied["puissance_traction_w"] == pytest.approx(80_000.0)

    traces = tracer_resolution_inconnues(report)
    assert isinstance(traces, list)
    assert any(trace["champ"] == "puissance_traction_w" for trace in traces)
