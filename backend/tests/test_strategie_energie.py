import pytest

from backend.ensemble.strategie_energie import (
    ModeEnergetique,
    analyser_strategie_energie,
    calculer_strategie_couplage,
    determiner_enveloppe_batterie,
    generer_cartographie_alternateur,
)


# Fixtures arbitraires de test uniquement.
# Elles ne representent pas des valeurs de conception SHSE-M.
FIXTURE_TEST_RENDEMENT_ALTERNATEUR = 0.92
FIXTURE_TEST_VBUS = 400.0
FIXTURE_TEST_CAP_AH = 100.0
FIXTURE_TEST_SOC_MIN = 0.2
FIXTURE_TEST_SOC_MAX = 0.9
FIXTURE_TEST_RPM_MIN = 1000.0
FIXTURE_TEST_RPM_MAX = 4000.0
FIXTURE_TEST_TOLERANCE_PUISSANCE = 0.05
FIXTURE_TEST_TOLERANCE_TRANSITOIRE = 0.1


def FIXTURE_LOI_SOH_ARBITRAIRE(p_crate: float, soh: float) -> float:
    """
    Fixture arbitraire de test.
    Ne represente pas une loi batterie SHSE-M.
    """
    return p_crate * soh


class _FakeBattery:
    tension_nominale_v = FIXTURE_TEST_VBUS
    tension_charge_v = 420.0
    capacite_ah = FIXTURE_TEST_CAP_AH
    c_rate_max_charge = 1.0
    temperature_alerte_c = 45.0


class _FakeBatteryWithSohLaw(_FakeBattery):
    loi_reduction_puissance_soh = staticmethod(FIXTURE_LOI_SOH_ARBITRAIRE)


class _FakeAlternateurWithCouple:
    pertes_fixes_w = 500.0

    def analyser_point_de_fonctionnement(self, vitesse_rotation_rpm, tension_v, couple_nm):
        omega = 2.0 * 3.141592653589793 * float(vitesse_rotation_rpm) / 60.0
        p_meca = float(couple_nm) * omega
        p_elec = p_meca * FIXTURE_TEST_RENDEMENT_ALTERNATEUR
        return {
            "pertes": {
                "pertes_cuivre_w": 800.0,
                "pertes_fer_w": 300.0,
                "pertes_fixes_w": 500.0,
                "pertes_connues_total_w": p_meca - p_elec,
            },
            "rendement": {"rendement": FIXTURE_TEST_RENDEMENT_ALTERNATEUR},
            "sortie_electrique": {"puissance_utile_w": p_elec, "tension_v": tension_v},
            "mecanique": {
                "puissance_mecanique_dimensionnante_w": p_meca,
                "couple_mecanique_dimensionnant_nm": couple_nm,
            },
            "thermique": {"ok_temperature_sur_pertes_connues": True},
            "inconnues": {"impossibles": [], "partielles": []},
        }


class _FakeAlternateurNoCouple:
    def analyser_point_de_fonctionnement(self, vitesse_rotation_rpm, tension_v):
        return {"inconnues": {"impossibles": [], "partielles": []}}


class _FakeAlternateurNoEta:
    def analyser_point_de_fonctionnement(self, vitesse_rotation_rpm, tension_v, couple_nm):
        omega = 2.0 * 3.141592653589793 * float(vitesse_rotation_rpm) / 60.0
        p_meca = float(couple_nm) * omega
        return {
            "pertes": {"pertes_cuivre_w": 100.0},
            "sortie_electrique": {"puissance_utile_w": None, "tension_v": tension_v},
            "mecanique": {"puissance_mecanique_dimensionnante_w": p_meca},
            "inconnues": {"impossibles": [], "partielles": []},
        }


class _FakeBox:
    rapports = [1.0, 1.5]


class _FakeBoxWithoutRatios:
    rapports = None


class _FakeEngine:
    rpm_min = FIXTURE_TEST_RPM_MIN
    rpm_max = FIXTURE_TEST_RPM_MAX


class _FakeEngineWithoutRange:
    rpm_min = None
    rpm_max = None


class _FakeDeplaceur:
    resistance_thermique_k_w = 0.2
    capacite_thermique_j_k = 100.0


def _candidate(
    *,
    ratio=1.0,
    p_out=50000.0,
    p_alt_loss=2000.0,
    p_alt_mec=54000.0,
    p_mt=56000.0,
    current=100.0,
):
    return {
        "rapport": ratio,
        "rpm_alternateur": 3000.0,
        "alternateur": {
            "bus_dc": {"courant_bus_dc_A": current},
            "thermique": {"ok_temperature_sur_pertes_connues": True},
            "mecanique": {
                "puissance_mecanique_dimensionnante_w": p_alt_mec,
                "couple_mecanique_dimensionnant_nm": 120.0,
            },
            "inconnues": {"impossibles": [], "partielles": []},
        },
        "boite": {"inconnues": {"impossibles": [], "partielles": []}},
        "exigences": {
            "P_out_W": p_out,
            "P_pertes_alternateur_W": p_alt_loss,
            "P_mecanique_alternateur_W": p_alt_mec,
            "puissance_moteur_requise_W": p_mt,
            "couple_moteur_requis_Nm": 180.0,
            "couple_moteur_min_theorique_Nm": 170.0,
        },
    }


def _components(
    *,
    battery=None,
    alternator=None,
    box=None,
    engine=None,
    deplaceur=None,
):
    return {
        "batterie": battery if battery is not None else _FakeBattery(),
        "alternateur": alternator if alternator is not None else _FakeAlternateurWithCouple(),
        "boite_crabots": box if box is not None else _FakeBox(),
        "moteur_thermique": engine if engine is not None else _FakeEngine(),
        "deplaceur": deplaceur if deplaceur is not None else _FakeDeplaceur(),
    }


def _state(**overrides):
    base = {
        "puissance_sortie_demandee_w": 45000.0,
        "puissance_elec_usage_w": 45000.0,
        "puissance_auxiliaire_w": 1000.0,
        "p_recharge_demandee_w": 0.0,
        "v_bus_dc_v": FIXTURE_TEST_VBUS,
        "temps_disponible_s": 1.0,
        "tolerance_puissance_relative": FIXTURE_TEST_TOLERANCE_PUISSANCE,
        "tolerance_transitoire_relative": FIXTURE_TEST_TOLERANCE_TRANSITOIRE,
    }
    base.update(overrides)
    return base


def test_sans_v_bus_dc_strategie_impossible_et_inconnue():
    rep = analyser_strategie_energie(
        etat_systeme=_state(v_bus_dc_v=None),
        composants=_components(),
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert any(item["nom"] == "v_bus_dc_v" for item in rep["inconnues"]["impossibles"])


def test_sans_rendement_moteur_electrique_pas_de_fallback_p_bus_egal_p_sortie():
    rep = analyser_strategie_energie(
        etat_systeme={
            "puissance_sortie_demandee_w": 45000.0,
            "puissance_auxiliaire_w": 1000.0,
            "v_bus_dc_v": FIXTURE_TEST_VBUS,
        },
        composants={"batterie": _FakeBattery()},
        derivees_chaine_energie={},
    )
    assert rep["bilan_bus_dc"]["puissance_electrique_usage_w"] is None
    assert any(item["nom"] == "p_traction_bus_dc_w" for item in rep["inconnues"]["partielles"])


def test_sans_loi_soh_p_charge_max_soh_reste_inconnue():
    rep = determiner_enveloppe_batterie(
        batterie=_FakeBattery(),
        etat_systeme={"batterie_temp_c": 25.0, "v_bus_dc_v": FIXTURE_TEST_VBUS, "batterie_soh": 0.8},
    )
    assert rep["enveloppe"]["p_charge_max_soh_w"] is None
    assert any("Loi de reduction de puissance" in item["raison"] for item in rep["inconnues"]["partielles"])


def test_batterie_trop_chaude_interdit_recharge():
    rep = calculer_strategie_couplage(
        etat_systeme=_state(p_recharge_demandee_w=10000.0, batterie_temp_c=50.0),
        composants=_components(),
    )
    assert rep["mode_energetique"] == ModeEnergetique.MODE_DEGRADE.value
    assert rep["enveloppe_batterie"]["p_charge_max_temp_w"] == 0.0
    assert rep["bilan_bus_dc"]["p_charge_cible_w"] == 0.0


def test_batterie_trop_chaude_mais_soutien_traction_autorise():
    rep = calculer_strategie_couplage(
        etat_systeme=_state(p_recharge_demandee_w=10000.0, batterie_temp_c=50.0),
        composants=_components(),
        autoriser_soutien_traction_si_recharge_interdite=True,
    )
    assert rep["mode_energetique"] == ModeEnergetique.SOUTIEN_TRACTION.value
    assert rep["bilan_bus_dc"]["p_charge_cible_w"] == 0.0


def test_cartographie_sans_bornes_est_impossible():
    rep = generer_cartographie_alternateur(
        alternateur=_FakeAlternateurWithCouple(),
        tension_bus_dc_v=FIXTURE_TEST_VBUS,
    )
    assert rep["points"] == []
    assert any(item["nom"] == "rpm_min" for item in rep["inconnues"]["impossibles"])


def test_api_alternateur_sans_couple_rend_la_cartographie_impossible():
    rep = generer_cartographie_alternateur(
        alternateur=_FakeAlternateurNoCouple(),
        tension_bus_dc_v=FIXTURE_TEST_VBUS,
        rpm_min=1000.0,
        rpm_max=1000.0,
        rpm_step=100.0,
        couple_min=10.0,
        couple_max=10.0,
        couple_step=5.0,
    )
    assert any(item["nom"] == "alternateur.couple_nm" for item in rep["inconnues"]["impossibles"])
    assert rep["points"] == []


def test_mode_lexicographique_prefere_le_point_moins_stressant_pour_la_batterie():
    rep = analyser_strategie_energie(
        etat_systeme=_state(),
        composants=_components(),
        rapport_boite={
            "candidats": [
                _candidate(ratio=1.0, p_alt_loss=1500.0, p_alt_mec=53000.0, p_mt=55000.0, current=140.0),
                _candidate(ratio=1.5, p_alt_loss=1800.0, p_alt_mec=54000.0, p_mt=56000.0, current=80.0),
            ]
        },
        point_actuel={"rpm": 1000.0, "couple_nm": 20.0},
    )
    assert rep["point_retenu"]["rapport"] == pytest.approx(1.5)


def test_sans_rapports_de_boite_remonte_une_inconnue_precise():
    rep = analyser_strategie_energie(
        etat_systeme=_state(),
        composants=_components(box=_FakeBoxWithoutRatios()),
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert any(item["nom"] == "boite_crabots.rapports" for item in rep["inconnues"]["impossibles"])


def test_sans_plage_rpm_moteur_thermique_remonte_une_inconnue_precise():
    rep = analyser_strategie_energie(
        etat_systeme=_state(),
        composants=_components(engine=_FakeEngineWithoutRange()),
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert any(item["nom"] == "moteur_thermique.rpm_min/rpm_max" for item in rep["inconnues"]["impossibles"])


def test_sans_tolerance_puissance_pas_de_filtrage_silencieux():
    rep = analyser_strategie_energie(
        etat_systeme=_state(tolerance_puissance_relative=None),
        composants=_components(),
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert rep["point_retenu"] is not None
    assert any(item["nom"] == "tolerance_puissance_relative" for item in rep["inconnues"]["partielles"])


def test_sans_tolerance_transitoire_retourne_un_statut_partiel():
    rep = analyser_strategie_energie(
        etat_systeme=_state(tolerance_transitoire_relative=None),
        composants=_components(),
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert rep["validation_transitoire"]["statut"] == "partiel"


def test_avec_toutes_les_donnees_decision_calculable():
    rep = analyser_strategie_energie(
        etat_systeme=_state(p_recharge_demandee_w=5000.0, batterie_soh=0.85, temp_derating_seuil_c=40.0),
        composants=_components(battery=_FakeBatteryWithSohLaw()),
        derivees_chaine_energie={
            "puissance_mecanique_alternateur_requise_w": 52000.0,
            "puissance_moteur_thermique_requise_w": 55000.0,
        },
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1200.0, "couple_nm": 40.0},
    )
    assert rep["decision"]["mode_energetique"] == ModeEnergetique.RECHARGE_BATTERIE.value
    assert rep["point_retenu"] is not None
    assert rep["enveloppe_batterie"]["p_charge_max_soh_w"] is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
