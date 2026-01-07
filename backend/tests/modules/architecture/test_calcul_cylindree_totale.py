# backend/tests/modules/architecture/test_calcul_cylindree_totale.py
import pytest
import os
import logging
import math
from backend.modules.architecture.calcul_cylindree_totale import (
    calcul_cylindree_totale_requise
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_architecture.log")
logger = logging.getLogger("test_architecture")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_cylindree_totale_requise():
    test_name = "test_calcul_cylindree_totale_requise"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: P = 100kW, PME = 10 bar (1e6 Pa), f=25Hz (3000 rpm 4T), eta=1.0
        # Vtot = 100e3 / (1.0 * 1e6 * 25) = 1e5 / 2.5e7 = 0.004 m3 (4L)
        res = calcul_cylindree_totale_requise(100e3, 10e5, 25.0, 1.0)
        assert abs(res - 0.004) < 1e-10
        
        # Avec rendement
        # Vtot = 100e3 / (0.8 * 10e5 * 25) = 1e5 / 2e7 = 0.005 m3 (5L)
        res = calcul_cylindree_totale_requise(100e3, 10e5, 25.0, 0.8)
        assert abs(res - 0.005) < 1e-10
        
        # Puissance nulle
        assert calcul_cylindree_totale_requise(0.0, 10e5, 25.0, 1.0) == 0.0
        
        # Erreurs
        with pytest.raises(ValueError):
            calcul_cylindree_totale_requise(-100.0, 10e5, 25.0)
        with pytest.raises(ValueError):
            calcul_cylindree_totale_requise(100e3, 0.0, 25.0)
        with pytest.raises(ValueError):
            calcul_cylindree_totale_requise(100e3, 10e5, 0.0)
        with pytest.raises(ValueError):
            calcul_cylindree_totale_requise(100e3, 10e5, 25.0, 0.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e