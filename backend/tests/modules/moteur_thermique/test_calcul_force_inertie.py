# backend/tests/modules/moteur_thermique/test_calcul_force_inertie.py
import pytest
import os
import logging
import math
from backend.components.moteur_thermique.modules.calcul_force_inertie import (
    calcul_force_inertie_alternative
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

def test_calcul_force_inertie_alternative():
    test_name = "test_calcul_force_inertie_alternative"
    logger.info(f"Starting {test_name}")
    try:
        # m=0.5kg, r=0.04m, n=3000rpm, l=0.15m, theta=0° (PMH)
        # omega = 3000 * 2pi / 60 = 100pi = 314.16 rad/s
        # Fi = 0.5 * 0.04 * (100pi)^2 * (cos(0) + 0.04/0.15 * cos(0))
        # Fi = 0.02 * 98696 * (1 + 0.2666) = 1973.92 * 1.2666 = 2500 N
        res = calcul_force_inertie_alternative(0.5, 0.04, 3000.0, 0.15, 0.0)
        assert abs(res - 2500.0) < 1.0
        
        # theta=180° (PMB)
        # Fi = 0.5 * 0.04 * (100pi)^2 * (cos(180) + 0.04/0.15 * cos(360))
        # Fi = 1973.92 * (-1 + 0.2666) = 1973.92 * -0.7333 = -1447.5 N
        res_pmb = calcul_force_inertie_alternative(0.5, 0.04, 3000.0, 0.15, 180.0)
        assert abs(res_pmb - (-1447.5)) < 1.0
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
