# backend/tests/modules/moteur_thermique/test_calcul_couple_vilebrequin.py
import pytest
import os
import logging
import math
from backend.components.moteur_thermique.modules.calcul_couple_vilebrequin import (
    calcul_couple_instantane
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

def test_calcul_couple_instantane():
    test_name = "test_calcul_couple_instantane"
    logger.info(f"Starting {test_name}")
    try:
        # F=1000N, r=0.05m, theta=90° => T = 1000 * 0.05 * sin(90°) = 50 Nm
        assert calcul_couple_instantane(1000.0, 0.05, 90.0) == 50.0
        
        # theta=0° => T=0
        assert calcul_couple_instantane(1000.0, 0.05, 0.0) == 0.0
        
        # Avec radians
        assert calcul_couple_instantane(1000.0, 0.05, math.pi/2, angle_unite="rad") == 50.0
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e