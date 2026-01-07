# backend/tests/modules/moteur_thermique/test_calcul_vitesse_piston.py
import pytest
import os
import logging
from backend.modules.moteur_thermique.calcul_vitesse_piston import (
    calcul_vitesse_moyenne_piston
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

def test_calcul_vitesse_moyenne_piston():
    test_name = "test_calcul_vitesse_moyenne_piston"
    logger.info(f"Starting {test_name}")
    try:
        # S=0.08m, n=3000rpm
        # Up = 2 * 0.08 * (3000/60) = 0.16 * 50 = 8 m/s
        assert calcul_vitesse_moyenne_piston(0.08, 3000.0) == 8.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
