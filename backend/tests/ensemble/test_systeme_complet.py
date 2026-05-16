import logging
import os
import pytest
import json
from unittest.mock import MagicMock
from backend.ensemble.systeme_complet import SystemeComplet
from backend.components.moteur_electrique.moteur_electrique import MoteurElectrique
from backend.components.batterie.batterie import Batterie
from backend.components.alternateur.alternateur import Alternateur
from backend.components.moteur_thermique.moteur_thermique import MoteurThermique

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
LOG_FILE = os.path.join(LOG_DIR, "test_systeme_complet.log")
logger = logging.getLogger("test_systeme_complet")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

@pytest.fixture
def mock_system():
    # Création d'instances réelles pour passer les checks isinstance
    moteur_elec = MoteurElectrique(
        puissance_max_w=100000.0,
        regime_max_rpm=6000.0,
        couple_max_nm=300.0,
        tension_bus_v=400.0,
        rendement_moteur=0.9,
        pertes_fixes_w=100.0
    )
    
    batterie = Batterie(
        tension_nominale_v=400.0,
        densite_energetique_kwh_kg=0.2, # 200 Wh/kg
        rendement_charge=0.95,
        tension_charge_v=420.0
    )
    
    alternateur = Alternateur(
        connexion="Y",
        nombre_poles=12
    )
    
    moteur_th = MoteurThermique(
        nombre_cylindres=4,
        temps_moteur=4,
        alesage_m=0.08,
        course_m=0.08
    )
    
    return SystemeComplet(
        moteur_electrique=moteur_elec,
        batterie=batterie,
        alternateur=alternateur,
        moteur_thermique=moteur_th
    )

def test_systeme_analyser_full(mock_system):
    logger.info("Starting test_systeme_analyser_full")
    try:
        rep = mock_system.analyser(
            masse_kg=1200.0,
            vitesse_ms=20.0,
            acceleration_ms2=0.5,
            coef_roulement=0.015,
            coef_trainee_aero_cda=0.65,
            rayon_roue_m=0.32,
            rapport_reduction_global=9.0,
            rendement_transmission=0.95,
            vitesse_moteur_thermique_rpm=3000.0,
            pme_pa=10e5 # 10 bar
        )
        
        assert "sous_systemes" in rep
        assert "traction" in rep["sous_systemes"]
        assert rep["sous_systemes"]["traction"] is not None
        
        # Log de l'ensemble des données en JSON
        logger.info("REPONSE DETAILLEE DU SYSTEME CLASSIQUE:")
        logger.info(json.dumps(rep, indent=2, ensure_ascii=False))
        
        log_test_result("test_systeme_analyser_full", "SUCCESS")
    except Exception as e:
        log_test_result("test_systeme_analyser_full", "FAILED", str(e))
        raise

def test_systeme_missing_inputs(mock_system):
    logger.info("Starting test_systeme_missing_inputs")
    try:
        # Analyse avec entrées minimales
        rep = mock_system.analyser()
        
        # On s'attend à des inconnues car pas d'entrées
        assert len(rep["inconnues"]["partielles"]) > 0
        
        log_test_result("test_systeme_missing_inputs", "SUCCESS")
    except Exception as e:
        log_test_result("test_systeme_missing_inputs", "FAILED", str(e))
        raise


def test_systeme_complet_auxiliaires_absents_ne_deviennent_pas_zero_en_mode_strict():
    moteur_th = MagicMock()
    moteur_th.temps_moteur = 4
    moteur_th.rendement_mecanique_nominal = 0.85
    moteur_th.facteur_securite_cylindre = 1.5
    moteur_th.rpm_nominal = 3000.0
    moteur_th.analyser_point_de_fonctionnement.return_value = {}

    systeme = SystemeComplet(moteur_thermique=moteur_th)
    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        vitesse_moteur_thermique_rpm=3000.0,
        pme_pa=10e5,
    )

    assert rep["sous_systemes"]["traction"]["puissance_auxiliaire_w"] is None
    assert any(item["nom"] == "puissance_auxiliaire_w" for item in rep["inconnues"]["partielles"])
    assert rep["synthese_detail"]["P_bus_dc_design_w"]["statut"] == "partiel"


def test_systeme_complet_traction_incomplete_ne_suppose_pas_zero():
    moteur_th = MagicMock()
    moteur_th.temps_moteur = 4
    moteur_th.rendement_mecanique_nominal = 0.85
    moteur_th.facteur_securite_cylindre = 1.5

    systeme = SystemeComplet(moteur_thermique=moteur_th)
    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        puissance_auxiliaire_w=0.0,
        vitesse_moteur_thermique_rpm=3000.0,
        pme_pa=10e5,
    )

    traction = rep["sous_systemes"]["traction"]["rapport_puissance"]
    assert traction["valeur"] is None
    assert traction["statut"] == "partiel"
    assert "acceleration_ms2" in traction["inconnues"]
    assert "coef_roulement" in traction["inconnues"]
    assert "coef_trainee_aero_cda" in traction["inconnues"]
    assert rep["synthese_detail"]["P_bus_dc_design_w"]["statut"] == "partiel"
    assert any(item["nom"] == "acceleration_ms2" for item in rep["inconnues"]["partielles"])


def test_systeme_complet_temps_moteur_absent_reste_inconnu():
    moteur_th = MagicMock()
    moteur_th.temps_moteur = None
    moteur_th.rendement_mecanique_nominal = 0.85
    moteur_th.facteur_securite_cylindre = 1.5
    moteur_th.definir_depuis_exigences = MagicMock()

    systeme = SystemeComplet(moteur_thermique=moteur_th)
    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        puissance_auxiliaire_w=0.0,
        vitesse_moteur_thermique_rpm=3000.0,
        pme_pa=10e5,
    )

    assert any(item["nom"] == "temps_moteur" for item in rep["inconnues"]["partielles"])
    moteur_th.definir_depuis_exigences.assert_not_called()


def test_systeme_complet_rendement_mecanique_absent_reste_inconnu():
    moteur_th = MagicMock()
    moteur_th.temps_moteur = 4
    moteur_th.rendement_mecanique_nominal = None
    moteur_th.facteur_securite_cylindre = 1.5
    moteur_th.definir_depuis_exigences = MagicMock()

    systeme = SystemeComplet(moteur_thermique=moteur_th)
    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        puissance_auxiliaire_w=0.0,
        vitesse_moteur_thermique_rpm=3000.0,
        pme_pa=10e5,
    )

    assert any(item["nom"] == "rendement_mecanique" for item in rep["inconnues"]["partielles"])
    moteur_th.definir_depuis_exigences.assert_not_called()
    assert rep["synthese_detail"]["P_moteur_thermique_W"]["statut"] == "partiel"


def test_systeme_complet_architecture_absente_non_consolidee_comme_ok():
    class FakeArchitecture:
        def analyser(self, **kwargs):
            return {"meilleur": {}}

    moteur_th = MagicMock()
    moteur_th.temps_moteur = 4
    moteur_th.rendement_mecanique_nominal = 0.85
    moteur_th.facteur_securite_cylindre = 1.5
    moteur_th.architecture = None
    moteur_th.definir_depuis_exigences.return_value = {"moteur_defini": moteur_th}
    moteur_th.analyser_point_de_fonctionnement.return_value = {"conception": {}, "resultats": {}, "dimensionnement": {}}

    systeme = SystemeComplet(moteur_thermique=moteur_th, architecture=FakeArchitecture())
    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        puissance_auxiliaire_w=0.0,
        vitesse_moteur_thermique_rpm=3000.0,
        pme_pa=10e5,
    )

    assert rep["synthese"]["moteur_thermique"]["architecture"] is None
    assert rep["synthese_detail"]["architecture"]["statut"] == "partiel"
    assert any(item["nom"] == "architecture" for item in rep["inconnues"]["partielles"])


def test_systeme_complet_puissance_thermique_non_calculee_si_rendement_manquant():
    moteur_th = MagicMock()
    moteur_th.temps_moteur = 4
    moteur_th.rendement_mecanique_nominal = None
    moteur_th.facteur_securite_cylindre = 1.5
    moteur_th.definir_depuis_exigences = MagicMock()
    moteur_th.analyser_point_de_fonctionnement.return_value = {"conception": {}, "resultats": {}, "dimensionnement": {}}

    systeme = SystemeComplet(moteur_thermique=moteur_th)
    rep = systeme.analyser(
        masse_kg=1200.0,
        vitesse_ms=20.0,
        acceleration_ms2=0.5,
        coef_roulement=0.015,
        coef_trainee_aero_cda=0.65,
        puissance_auxiliaire_w=0.0,
        vitesse_moteur_thermique_rpm=3000.0,
        pme_pa=10e5,
    )

    assert rep["synthese"]["moteur_thermique"]["puissance_requise_W"] is None
    assert any(item["nom"] == "puissance_moteur_thermique_requise_W" for item in rep["inconnues"]["partielles"])

if __name__ == "__main__":
    pytest.main([__file__])
