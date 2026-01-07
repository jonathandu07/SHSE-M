# backend/tests/modules/moteur_electrique/test_calcul_acceleration_max.py
import pytest
import os
import logging
import math
from backend.modules.moteur_electrique.calcul_acceleration_max import (
    calcul_acceleration_max,
    calcul_acceleration_max_analytique
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

def test_calcul_acceleration_max():
    test_name = "test_calcul_acceleration_max"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: mu=0.8, N_drive=10000N, Fres=1000N, m=1500kg
        # F_traction = 0.8 * 10000 = 8000N
        # a = (8000 - 1000) / 1500 = 7000 / 1500 = 4.66 m/s2
        res = calcul_acceleration_max(0.8, 10000.0, 1000.0, 1500.0, 0.5, 2.5, "fwd")
        assert abs(res - 4.666666666) < 1e-7
        
        # Avec transfert (FWD)
        # a = (mu*N_static - Fres) / (m*(1 + mu*h/L))
        # N_static = 10000N
        # denom = 1500 * (1 + 0.8 * 0.5 / 2.5) = 1500 * (1 + 0.4 / 2.5) = 1500 * 1.16 = 1740
        # a = 7000 / 1740 = 4.02 m/s2
        res_t = calcul_acceleration_max(0.8, 10000.0, 1000.0, 1500.0, 0.5, 2.5, "fwd", include_transfert=True)
        assert abs(res_t - (7000.0/1740.0)) < 1e-7
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_acceleration_max_analytique():
    test_name = "test_calcul_acceleration_max_analytique"
    logger.info(f"Starting {test_name}")
    try:
        # m=1500, g=9.81, lr=1.5, lf=1.0, h=0.5, L=2.5, theta=0, Fres=1000, mu=0.8, mode=FWD
        # numer = 0.8 * (9.81 * 1 * 1.5 / 2.5) - (1000 / 1500) = 0.8 * 5.886 - 0.666 = 4.7088 - 0.666 = 4.042
        # denom = 1 + 0.8 * 0.5 / 2.5 = 1.16
        # a = 4.042 / 1.16 = 3.48 m/s2 (approx)
        res = calcul_acceleration_max_analytique(0.8, 1500.0, 9.81, 1.5, 1.0, 0.5, 2.5, 0.0, 1000.0, "FWD")
        assert res > 0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e