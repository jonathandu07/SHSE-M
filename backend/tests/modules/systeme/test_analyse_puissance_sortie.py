import pytest

from backend.modules.systeme.analyse_puissance_sortie import (
    analyser_puissance_sortie,
    normaliser_puissance,
    optimiser_puissance_sortie,
)


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


def test_optimizer_does_not_choose_without_search_space():
    report = optimiser_puissance_sortie(100, "kw")

    assert report["resume"]["nb_candidats"] == 1
    assert report["selection"] == {}
    unknown_names = {item["nom"] for item in report["inconnues"]["partielles"]}
    assert "rpm_sortie" in unknown_names
    assert "tension_dc_v" in unknown_names
    assert "couple_sortie_max" in unknown_names
    assert "courant_dc_min" in unknown_names


def test_optimizer_selects_best_values_from_provided_vectors_only():
    report = optimiser_puissance_sortie(
        100,
        "kw",
        espace_recherche={
            "rpm_sortie": [1000.0, 2000.0, 4000.0],
            "tension_dc_v": [300.0, 400.0, 800.0],
        },
    )

    assert report["resume"]["nb_candidats"] == 9
    assert report["selection"]["couple_sortie_max"]["valeur"] == pytest.approx(954.9296586)
    assert report["selection"]["couple_sortie_max"]["candidat"]["entrees"]["rpm_sortie"] == 1000.0
    assert report["selection"]["courant_dc_min"]["valeur"] == pytest.approx(125.0)
    assert report["selection"]["courant_dc_min"]["candidat"]["entrees"]["tension_dc_v"] == 800.0


def test_optimizer_applies_explicit_constraints():
    report = optimiser_puissance_sortie(
        100,
        "kw",
        espace_recherche={
            "rpm_sortie": [1000.0, 2000.0],
            "tension_dc_v": [400.0, 800.0],
        },
        contraintes={"courant_dc_a_max": 200.0},
    )

    assert report["resume"]["nb_candidats"] == 4
    assert report["resume"]["nb_candidats_valides"] == 2
    assert report["selection"]["courant_dc_min"]["valeur"] == pytest.approx(125.0)
    assert all(item["entrees"]["tension_dc_v"] == 800.0 for item in report["candidats_valides"])


def test_optimizer_can_select_engine_geometry_when_all_inputs_are_candidates():
    report = optimiser_puissance_sortie(
        100,
        "kw",
        donnees_connues={
            "rendement_sortie_depuis_moteur": 0.95,
            "type_puissance_moteur": "frein",
            "rendement_mecanique": 0.9,
            "temps_moteur": 4,
            "pression_max_pa": 6.0e6,
            "contrainte_admissible_pa": 300.0e6,
            "facteur_securite_cylindre": 1.5,
        },
        espace_recherche={
            "rpm_moteur": [2000.0, 3000.0],
            "pme_pa": [900000.0, 1200000.0],
            "nombre_cylindres": [4, 6],
            "ratio_course_alesage_cible": [1.0],
        },
    )

    assert report["resume"]["nb_candidats"] == 8
    assert report["selection"]["cylindree_min"]["valeur"] == pytest.approx(3.8986355)
    assert report["selection"]["cylindree_min"]["candidat"]["entrees"]["rpm_moteur"] == 3000.0
    assert report["selection"]["cylindree_min"]["candidat"]["entrees"]["pme_pa"] == 1200000.0
    assert report["resume"]["pret_pour_dimensionnement_pieces"] is True
