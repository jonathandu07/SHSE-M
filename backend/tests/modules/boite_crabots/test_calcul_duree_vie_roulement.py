# backend/tests/modules/boite_crabots/test_calcul_duree_vie_roulement.py
import pytest
import os
import logging
import math
from backend.modules.boite_crabots.calcul_duree_vie_roulement import (
    calcul_charge_equivalente_roulement,
    calcul_duree_vie_l10,
    calcul_duree_vie_heures
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

def test_calcul_charge_equivalente_roulement():
    test_name = "test_calcul_charge_equivalente_roulement"
    logger.info(f"Starting {test_name}")
    try:
        # Fr=1000, Fa=500, X=0.56, Y=1.45 => P = 0.56*1000 + 1.45*500 = 560 + 725 = 1285N
        res = calcul_charge_equivalente_roulement(1000.0, 500.0, 0.56, 1.45)
        assert res == 1285.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_duree_vie_l10():
    test_name = "test_calcul_duree_vie_l10"
    logger.info(f"Starting {test_name}")
    try:
        # C=10000N, P=1000N, bille (p=3) => L10 = (10000/1000)^3 = 10^3 = 1000 millions de tours
        assert calcul_duree_vie_l10(10000.0, 1000.0, "bille") == 1000.0
        # P=0 => vie infinie
        assert calcul_duree_vie_l10(10000.0, 0.0, "bille") == float("inf")
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_duree_vie_heures():
    test_name = "test_calcul_duree_vie_heures"
    logger.info(f"Starting {test_name}")
    try:
        # L10=60 millions, n=1000 tr/min => L10h = (10^6 * 60) / (60 * 1000) = 60,000,000 / 60,000 = 1000 h
        assert calcul_duree_vie_heures(60.0, 1000.0) == 1000.0
        # L10=inf => L10h=inf
        assert calcul_duree_vie_heures(float("inf"), 1000.0) == float("inf")
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e