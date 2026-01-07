import logging
import os
import pytest
from unittest.mock import MagicMock
from backend.ensemble.systeme_complet import SystemeComplet

# Configuration du logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "test_systeme_complet.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding="utf-8"
)
logger = logging.getLogger("test_systeme_complet")

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

@pytest.fixture
def mock_system():
    # Création de mocks pour les composants
    moteur_elec = MagicMock()
    moteur_elec.rendement_moteur = 0.9
    moteur_elec.pertes_fixes_w = 100.0
    moteur_elec.tension_bus_v = 400.0
    
    batterie = MagicMock()
    batterie.tension_nominale_v = 400.0
    batterie.analyser_dimensionnement.return_value = {"dimensionnement": {"E_utile_finale_kwh": 50.0}}
    
    alternateur = MagicMock()
    alternateur.analyser_pour_bus_dc.return_value = {"resultats": {"couple_mecanique_Nm": 50.0, "P_mecanique_W": 15000.0}}
    
    moteur_th = MagicMock()
    moteur_th.alesage_m = 0.08
    moteur_th.course_m = 0.08
    moteur_th.nombre_cylindres = 1
    moteur_th.temps_moteur = 4
    moteur_th.analyser_point_de_fonctionnement.return_value = {"resultat": "OK"}
    
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

if __name__ == "__main__":
    pytest.main([__file__])