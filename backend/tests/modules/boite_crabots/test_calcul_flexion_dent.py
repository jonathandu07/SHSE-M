# backend/tests/modules/boite_crabots/test_calcul_flexion_dent.py
import pytest
import os
import logging
from backend.modules.boite_crabots.calcul_flexion_dent import (
    calcul_contrainte_flexion_lewis
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_boite_crabots.log")
logger = logging.getLogger("test_boite_crabots")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_contrainte_flexion_lewis():
    test_name = "test_calcul_contrainte_flexion_lewis"
    logger.info(f"Starting {test_name}")
    try:
        # Ft=1000, b=0.02, m=0.002, Y=0.3
        # sigma = 1000 / (0.02 * 0.002 * 0.3) = 1000 / 0.000012 = 83.33 MPa
        res = calcul_contrainte_flexion_lewis(1000.0, 0.02, 0.002, 0.3)
        assert abs(res - 83333333.33) < 1.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e