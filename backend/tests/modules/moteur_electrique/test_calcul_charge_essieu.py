# backend/tests/modules/moteur_electrique/test_calcul_charge_essieu.py
import pytest
import os
import logging
import math
from backend.modules.moteur_electrique.calcul_charge_essieu import (
    calcul_charges_essieux
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

def test_calcul_charges_essieux():
    test_name = "test_calcul_charges_essieux"
    logger.info(f"Starting {test_name}")
    try:
        # Statique, plat: m=1500, a=0, theta=0, L=2.5, lr=1.5, lf=1.0, h=0.5
        # Nf = 1500 * 9.81 * 1.5 / 2.5 = 8829 N
        # Nr = 1500 * 9.81 * 1.0 / 2.5 = 5886 N
        res = calcul_charges_essieux(1500.0, 0.0, 0.0, 2.5, 1.5, 1.0, 0.5, 9.81)
        assert abs(res["N_avant"] - 8829.0) < 1e-7
        assert abs(res["N_arriere"] - 5886.0) < 1e-7
        
        # Accélération a=2.0 m/s2
        # Transfert = m*a*h/L = 1500 * 2 * 0.5 / 2.5 = 600 N
        # Nf = 8829 - 600 = 8229 N
        # Nr = 5886 + 600 = 6486 N
        res_a = calcul_charges_essieux(1500.0, 2.0, 0.0, 2.5, 1.5, 1.0, 0.5, 9.81)
        assert abs(res_a["N_avant"] - 8229.0) < 1e-7
        assert abs(res_a["N_arriere"] - 6486.0) < 1e-7
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e