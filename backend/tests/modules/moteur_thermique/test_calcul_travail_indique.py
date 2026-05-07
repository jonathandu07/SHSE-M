# backend/tests/modules/moteur_thermique/test_calcul_travail_indique.py
import pytest
import os
import logging
from backend.components.moteur_thermique.modules.calcul_travail_indique import (
    calcul_travail_indique_pme,
    calcul_puissance_indiquee
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_moteur_thermique.log")
logger = logging.getLogger("test_moteur_thermique")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_travail_indique_pme():
    test_name = "test_calcul_travail_indique_pme"
    logger.info(f"Starting {test_name}")
    try:
        # PME=10bar=1e6Pa, Vd=0.0005m3 => Wi = 500 J
        assert calcul_travail_indique_pme(1e6, 0.0005) == 500.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_puissance_indiquee():
    test_name = "test_calcul_puissance_indiquee"
    logger.info(f"Starting {test_name}")
    try:
        # Wi=500J, n=3000rpm, 4-temps
        # P = 500 * (3000/60/2) = 500 * 25 = 12500 W = 12.5 kW
        assert calcul_puissance_indiquee(500.0, 3000.0, 4) == 12500.0
        # 2-temps
        # P = 500 * (3000/60) = 25000 W = 25 kW
        assert calcul_puissance_indiquee(500.0, 3000.0, 2) == 25000.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
