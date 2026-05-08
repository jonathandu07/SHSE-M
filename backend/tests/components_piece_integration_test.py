from backend.components.batterie.batterie import Batterie
from backend.components.moteur_electrique.moteur_electrique import MoteurElectrique


def test_batterie_report_includes_piece_reports():
    batterie = Batterie(
        fenetre_soc=0.8,
        densite_energetique_kwh_kg=0.18,
        rendement_charge=0.92,
        puissance_charge_kw=22.0,
        tension_nominale_v=400.0,
    )

    report = batterie.analyser_dimensionnement(
        energie_utile_imposee_kwh=24.0,
        puissance_moyenne_kw=30.0,
        temps_charge_cible_h=2.0,
    )

    assert "pieces" in report
    assert sorted(report["pieces"]) == ["boitier", "busbars", "pack"]
    assert report["pieces"]["pack"]["piece"] == "pack_batterie"


def test_moteur_electrique_supports_component_level_report_without_external_config():
    moteur = MoteurElectrique(
        puissance_max_w=50000.0,
        regime_max_rpm=12000.0,
        couple_max_nm=180.0,
        rendement_moteur=0.94,
        tension_bus_v=400.0,
        courant_max_a=220.0,
    )

    report = moteur.analyser()

    assert report["definition"]["couple_max_nm"] == 180.0
    assert report["definition"]["regime_base_rpm"] > 0.0
    assert "pieces" in report
    assert sorted(report["pieces"]) == ["rotor", "stator"]
    assert report["pieces"]["stator"]["electrique"]["puissance_dc_max_w"] == 88000.0
