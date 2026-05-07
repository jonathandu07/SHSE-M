# backend/tests/modules/moteur_electrique/test_calcul_force_resistance_vitesse.py
import pytest
import os
import logging
import math
from backend.components.moteur_electrique.modules.calcul_force_resistance_vitesse import (
    calcul_force_resistance_totale
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

def test_calcul_force_resistance_totale():
    test_name = "test_calcul_force_resistance_totale"
    logger.info(f"Starting {test_name}")
    try:
        # m=1500, v=27.78 (100km/h), theta=0, Crr=0.01, CdA=0.6, rho=1.2, g=9.81
        # Fr = 1500 * 9.81 * 0.01 * 1 = 147.15 N
        # Fa = 0.5 * 1.2 * 0.6 * 27.78^2 = 0.36 * 771.7 = 277.8 N
        # Fp = 0
        res = calcul_force_resistance_totale(1500.0, 27.78, 0.0, 0.01, 0.6, 1.2, 9.81)
        assert abs(res["F_roulement"] - 147.15) < 1e-2
        assert abs(res["F_aero"] - 277.8) < 1.0
        assert res["F_pente"] == 0.0
        
        # Avec pente montée (10%)
        # theta = arctan(0.1) = 0.09967 rad
        # Fp = 1500 * 9.81 * sin(0.09967) = 14715 * 0.0995 = 1464 N
        res_p = calcul_force_resistance_totale(1500.0, 27.78, 10.0, 0.01, 0.6, 1.2, 9.81, angle_unite="deg")
        assert res_p["F_pente"] > 1000.0
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e