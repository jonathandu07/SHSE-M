# backend/tests/modules/moteur_thermique/test_calcul_precharge_vis.py
import pytest
import os
import logging
from backend.components.moteur_thermique.modules.calcul_precharge_vis import (
    calcul_force_separation,
    calcul_precharge_vis_totale,
    calcul_couple_serrage
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

def test_calcul_force_separation():
    test_name = "test_calcul_force_separation"
    logger.info(f"Starting {test_name}")
    try:
        # p=10MPa, A=0.01m2 => F = 100000 N
        assert calcul_force_separation(10e6, 0.01) == 100000.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_precharge_vis_totale():
    test_name = "test_calcul_precharge_vis_totale"
    logger.info(f"Starting {test_name}")
    try:
        # F_sep=100000, F_joint=20000, gamma=1.5 => F_pre = 150000 + 20000 = 170000 N
        assert calcul_precharge_vis_totale(100000.0, 20000.0, 1.5) == 170000.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_couple_serrage():
    test_name = "test_calcul_couple_serrage"
    logger.info(f"Starting {test_name}")
    try:
        # F=10000N, d=0.01m, K=0.2 => M = 0.2 * 10000 * 0.01 = 20 Nm
        assert calcul_couple_serrage(10000.0, 0.01) == 20.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
