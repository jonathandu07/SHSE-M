# backend/tests/modules/batterie/test_calcul_temps_charge.py
import pytest
import os
import logging
from backend.modules.batterie.calcul_temps_charge import (
    calcul_temps_charge
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

def test_calcul_temps_charge():
    test_name = "test_calcul_temps_charge"
    logger.info(f"Starting {test_name}")
    try:
        # 100kWh utiles, 50kW charge, 80% rendement => 100 / (50 * 0.8) = 2.5h
        assert calcul_temps_charge(100.0, 50.0, 0.8) == 2.5
        
        # Rien à charger
        assert calcul_temps_charge(0.0, 50.0, 0.8) == 0.0
        
        # Erreurs
        with pytest.raises(ValueError):
            calcul_temps_charge(100.0, 0.0, 0.8)
        with pytest.raises(ValueError):
            calcul_temps_charge(100.0, 50.0, 0.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e