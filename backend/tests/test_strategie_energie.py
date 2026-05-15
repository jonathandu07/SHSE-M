import pytest

from backend.ensemble.strategie_energie import (
    ModeEnergetique,
    analyser_strategie_energie,
    calculer_strategie_couplage,
    determiner_enveloppe_batterie,
    generer_cartographie_alternateur,
)


class _FakeBattery:
    tension_nominale_v = 400.0
    tension_charge_v = 420.0
    capacite_ah = 100.0
    c_rate_max_charge = 1.0
    puissance_charge_kw = 40.0
    temperature_alerte_c = 45.0


class _FakeAlternateur:
    rendement_alternateur_impose = 0.92
    pertes_fixes_w = 500.0

    def analyser_point_de_fonctionnement(self, **kwargs):
        p_out = kwargs.get("puissance_electrique_cible_w")
        rpm = kwargs.get("vitesse_rotation_rpm")
        return {
            "pertes": {
                "pertes_cuivre_w": 800.0,
                "pertes_fer_w": 300.0,
                "pertes_fixes_w": 500.0,
                "pertes_connues_total_w": 1600.0,
            },
            "rendement": {
                "rendement_impose": self.rendement_alternateur_impose,
                "eta_sur_pertes_connues": self.rendement_alternateur_impose,
            },
            "sortie_electrique": {
                "puissance_utile_w": p_out,
                "tension_v": kwargs.get("tension_v"),
            },
            "mecanique": {
                "puissance_mecanique_dimensionnante_w": (p_out / self.rendement_alternateur_impose) if p_out is not None else None,
                "couple_mecanique_dimensionnant_nm": 120.0 if rpm else None,
            },
            "thermique": {
                "ok_temperature_sur_pertes_connues": True,
            },
            "inconnues": {"impossibles": [], "partielles": []},
        }


class _FakeAlternateurNoEta(_FakeAlternateur):
    rendement_alternateur_impose = None


class _FakeBox:
    pass


class _FakeEngine:
    pass


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
    unknowns=None,
):
    unknowns = unknowns or {"impossibles": [], "partielles": []}
    return {
        "rapport": ratio,
        "rpm_alternateur": 3000.0,
        "alternateur": {
            "bus_dc": {"courant_bus_dc_A": current},
            "thermique": {"ok_temperature_sur_pertes_connues": True},
            "inconnues": unknowns,
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


def test_strategie_sans_soh_remonte_inconnue_partielle():
    rep = determiner_enveloppe_batterie(
        batterie=_FakeBattery(),
        etat_systeme={"batterie_temp_c": 25.0, "v_bus_dc_v": 420.0},
    )
    noms = {item["nom"] for item in rep["inconnues"]["partielles"]}
    assert "p_charge_max_soh_w" in noms


def test_strategie_sans_resistance_interne_laisse_les_pertes_joule_inconnues_sans_blocage():
    rep = analyser_strategie_energie(
        etat_systeme={
            "puissance_sortie_demandee_w": 40000.0,
            "puissance_elec_usage_w": 40000.0,
            "p_recharge_demandee_w": 0.0,
            "v_bus_dc_v": 400.0,
            "temps_disponible_s": 1.0,
        },
        composants={"batterie": _FakeBattery(), "alternateur": _FakeAlternateur(), "boite_crabots": _FakeBox(), "moteur_thermique": _FakeEngine(), "deplaceur": _FakeDeplaceur()},
        rapport_boite={"candidats": [_candidate()]},
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert rep["point_retenu"] is not None
    assert any(item["nom"] == "pertes_joule_batterie_w" for item in rep["inconnues"]["partielles"])


def test_batterie_trop_chaude_interdit_recharge():
    rep = calculer_strategie_couplage(
        etat_systeme={
            "puissance_sortie_demandee_w": 30000.0,
            "puissance_elec_usage_w": 30000.0,
            "p_recharge_demandee_w": 10000.0,
            "batterie_temp_c": 50.0,
            "v_bus_dc_v": 420.0,
        },
        composants={"batterie": _FakeBattery()},
    )
    assert rep["mode_energetique"] == ModeEnergetique.MODE_DEGRADE.value
    assert rep["bilan_bus_dc"]["puissance_recharge_retenue_w"] == 0.0


def test_batterie_trop_chaude_mais_soutien_traction_autorise():
    rep = calculer_strategie_couplage(
        etat_systeme={
            "puissance_sortie_demandee_w": 30000.0,
            "puissance_elec_usage_w": 30000.0,
            "p_recharge_demandee_w": 10000.0,
            "batterie_temp_c": 50.0,
            "v_bus_dc_v": 420.0,
        },
        composants={"batterie": _FakeBattery()},
        autoriser_soutien_traction_si_recharge_interdite=True,
    )
    assert rep["mode_energetique"] == ModeEnergetique.SOUTIEN_TRACTION.value
    assert rep["bilan_bus_dc"]["puissance_recharge_retenue_w"] == 0.0


def test_cartographie_alternateur_sans_bornes_est_impossible():
    rep = generer_cartographie_alternateur(alternateur=_FakeAlternateur(), tension_bus_dc_v=400.0)
    assert rep["points"] == []
    assert any(item["nom"] == "grille_rpm" for item in rep["inconnues"]["impossibles"])


def test_lexicographie_prefere_le_point_moins_stressant_pour_la_batterie():
    rep = analyser_strategie_energie(
        etat_systeme={
            "puissance_sortie_demandee_w": 45000.0,
            "puissance_elec_usage_w": 45000.0,
            "p_recharge_demandee_w": 0.0,
            "v_bus_dc_v": 400.0,
            "temps_disponible_s": 1.0,
        },
        composants={"batterie": _FakeBattery(), "alternateur": _FakeAlternateur(), "boite_crabots": _FakeBox(), "moteur_thermique": _FakeEngine(), "deplaceur": _FakeDeplaceur()},
        rapport_boite={
            "candidats": [
                _candidate(ratio=1.0, p_alt_loss=1500.0, p_alt_mec=53000.0, p_mt=55000.0, current=140.0),
                _candidate(ratio=1.5, p_alt_loss=1800.0, p_alt_mec=54000.0, p_mt=56000.0, current=80.0),
            ]
        },
        point_actuel={"rpm": 1000.0, "couple_nm": 20.0},
    )
    assert rep["point_retenu"]["rapport"] == pytest.approx(1.5)


def test_absence_de_rendement_alternateur_rend_la_cartographie_partielle():
    rep = generer_cartographie_alternateur(
        alternateur=_FakeAlternateurNoEta(),
        tension_bus_dc_v=400.0,
        rpm_min=1000.0,
        rpm_max=1000.0,
        rpm_step=500.0,
        couple_min=50.0,
        couple_max=50.0,
        couple_step=25.0,
    )
    assert rep["points"][0]["puissance_electrique_w"] is None
    assert rep["points"][0]["statut"] == "partiel"


def test_absence_de_rendement_boite_ou_liaison_remonte_une_inconnue_partielle():
    rep = analyser_strategie_energie(
        etat_systeme={
            "puissance_sortie_demandee_w": 45000.0,
            "puissance_elec_usage_w": 45000.0,
            "p_recharge_demandee_w": 0.0,
            "v_bus_dc_v": 400.0,
            "temps_disponible_s": 1.0,
        },
        composants={"batterie": _FakeBattery(), "alternateur": _FakeAlternateur(), "boite_crabots": _FakeBox(), "moteur_thermique": _FakeEngine(), "deplaceur": _FakeDeplaceur()},
        rapport_boite={
            "candidats": [
                {
                    "rapport": 1.0,
                    "rpm_alternateur": 3000.0,
                    "alternateur": {"bus_dc": {"courant_bus_dc_A": 90.0}, "inconnues": {"impossibles": [], "partielles": []}},
                    "boite": {"inconnues": {"impossibles": [], "partielles": []}},
                    "exigences": {
                        "P_out_W": 45000.0,
                        "P_pertes_alternateur_W": 1500.0,
                        "P_mecanique_alternateur_W": None,
                        "puissance_moteur_requise_W": None,
                        "puissance_moteur_min_theorique_W": None,
                        "couple_moteur_requis_Nm": 150.0,
                        "couple_moteur_min_theorique_Nm": 140.0,
                    },
                }
            ]
        },
        point_actuel={"rpm": 1000.0, "couple_nm": 10.0},
    )
    assert any(item["nom"] == "puissance_moteur_thermique_requise_w" for item in rep["inconnues"]["partielles"])
