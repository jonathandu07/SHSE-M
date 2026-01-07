# backend/tests/modules/moteur_electrique/test_calcul_puissance_roue.py
import pytest
import os
import logging
from backend.modules.moteur_electrique.calcul_puissance_roue import (
    calcul_puissance_roue,
    calcul_couple_roue_total,
    calcul_couple_par_roue
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_moteur_electrique.log")
logger = logging.getLogger("test_moteur_electrique")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_puissance_roue():
    test_name = "test_calcul_puissance_roue"
    logger.info(f"Starting {test_name}")
    try:
        # F=3000N, v=20m/s => P=60kW
        assert calcul_puissance_roue(3000.0, 20.0) == 60000.0
        assert calcul_puissance_roue(-3000.0, 20.0) == -60000.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_couple_roue_total():
    test_name = "test_calcul_couple_roue_total"
    logger.info(f"Starting {test_name}")
    try:
        # F=3000N, R=0.3m => T=900Nm
        assert calcul_couple_roue_total(3000.0, 0.3) == 900.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_couple_par_roue():
    test_name = "test_calcul_couple_par_roue"
    logger.info(f"Starting {test_name}")
    try:
        assert calcul_couple_par_roue(1000.0, 4) == 250.0
        with pytest.raises(ValueError):
             calcul_couple_par_roue(1000.0, 0)
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e