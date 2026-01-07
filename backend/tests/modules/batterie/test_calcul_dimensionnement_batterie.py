# backend/tests/modules/batterie/test_calcul_dimensionnement_batterie.py
import pytest
import os
import logging
from backend.modules.batterie.calcul_dimensionnement_batterie import (
    calcul_capacite_totale_batterie,
    calcul_poids_batterie
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_batterie.log")
logger = logging.getLogger("test_batterie")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_capacite_totale_batterie():
    test_name = "test_calcul_capacite_totale_batterie"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: 60kWh utiles, 80% SOC => 60/0.8 = 75kWh
        assert calcul_capacite_totale_batterie(60.0, 0.8) == 75.0
        
        # Energie nulle
        assert calcul_capacite_totale_batterie(0.0, 0.8) == 0.0
        
        # Erreurs
        with pytest.raises(ValueError):
            calcul_capacite_totale_batterie(-10.0, 0.8)
        with pytest.raises(ValueError):
            # SOC window must be > 0
            calcul_capacite_totale_batterie(60.0, 0.0)
        with pytest.raises(ValueError):
            # SOC window must be <= 1.0
            calcul_capacite_totale_batterie(60.0, 1.1)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_poids_batterie():
    test_name = "test_calcul_poids_batterie"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: 100kWh, 0.2kWh/kg => 100/0.2 = 500kg
        assert calcul_poids_batterie(100.0, 0.2) == 500.0
        
        # Capacité nulle
        assert calcul_poids_batterie(0.0, 0.2) == 0.0
        
        # Erreurs
        with pytest.raises(ValueError):
            calcul_poids_batterie(-10.0, 0.2)
        with pytest.raises(ValueError):
            # Density must be > 0
            calcul_poids_batterie(100.0, 0.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e