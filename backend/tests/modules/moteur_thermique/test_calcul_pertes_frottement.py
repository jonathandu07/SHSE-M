# backend/tests/modules/moteur_thermique/test_calcul_pertes_frottement.py
import pytest
import os
import logging
from backend.components.moteur_thermique.modules.calcul_pertes_frottement import (
    calcul_puissance_frottement_segment,
    calcul_puissance_frottement_palier
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

def test_calcul_puissance_frottement_segment():
    test_name = "test_calcul_puissance_frottement_segment"
    logger.info(f"Starting {test_name}")
    try:
        # N=1000N, v=10m/s, mu=0.05 => P = 0.05 * 1000 * 10 = 500 W
        assert calcul_puissance_frottement_segment(1000.0, 10.0, 0.05) == 500.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_puissance_frottement_palier():
    test_name = "test_calcul_puissance_frottement_palier"
    logger.info(f"Starting {test_name}")
    try:
        # W=5000N, v=5m/s, f=0.02 => P = 0.02 * 5000 * 5 = 500 W
        assert calcul_puissance_frottement_palier(5000.0, 5.0, 0.02) == 500.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
