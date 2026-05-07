import pytest

from backend.power_definition import analyser_puissance_sortie, normaliser_puissance


def test_normaliser_puissance_accepts_kw_and_metric_horsepower():
    assert normaliser_puissance(100, "kw")["w"] == pytest.approx(100000.0)
    assert normaliser_puissance(200, "ch")["kw"] == pytest.approx(147.09975)


def test_power_only_does_not_invent_engine_geometry():
    report = analyser_puissance_sortie(200, "ch")

    assert report["meta"]["mode"] == "puissance_sortie_strict_sans_invention"
    assert report["calculs"]["puissance_sortie"]["kw"] == pytest.approx(147.09975)
    assert "moteur_thermique" not in report["calculs"]
    assert report["niveau_definition"]["pret_pour_dimensionnement_pieces"] is False

    unknown_names = {item["nom"] for item in report["inconnues"]["impossibles"]}
    assert "cylindree moteur thermique" in unknown_names
    assert "type_puissance_moteur" in unknown_names


def test_known_engine_inputs_unlock_displacement_and_geometry():
    report = analyser_puissance_sortie(
        100,
        "kw",
        donnees_connues={
            "rendement_sortie_depuis_moteur": 0.95,
            "rpm_moteur": 3000.0,
            "pme_pa": 900000.0,
            "temps_moteur": 4,
            "type_puissance_moteur": "frein",
            "rendement_mecanique": 0.9,
            "nombre_cylindres": 4,
            "ratio_course_alesage_cible": 1.0,
            "pression_max_pa": 6.0e6,
            "contrainte_admissible_pa": 300.0e6,
            "facteur_securite_cylindre": 1.5,
        },
    )

    mt = report["calculs"]["moteur_thermique"]
    assert mt["cylindree_totale_requise_l"] == pytest.approx(5.1981806)
    assert mt["geometrie"]["nombre_cylindres"] == 4
    assert mt["geometrie"]["alesage_mm"] == pytest.approx(mt["geometrie"]["course_mm"])
    assert mt["epaisseur_cylindre_mince_m"] > 0.0
    assert report["niveau_definition"]["pret_pour_dimensionnement_pieces"] is True


def test_known_voltage_and_rpm_unlock_current_and_torque():
    report = analyser_puissance_sortie(
        50,
        "kw",
        donnees_connues={"rpm_sortie": 2500.0, "tension_dc_v": 400.0},
    )

    assert report["calculs"]["couple_sortie_nm"] == pytest.approx(190.9859317)
    assert report["calculs"]["courant_dc_a"] == pytest.approx(125.0)
