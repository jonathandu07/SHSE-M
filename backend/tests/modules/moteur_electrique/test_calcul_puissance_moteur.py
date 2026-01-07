# backend/tests/modules/moteur_electrique/test_calcul_puissance_moteur.py
import pytest
import os
import logging
from backend.modules.moteur_electrique.calcul_puissance_moteur import (
    calcul_puissance_moteur_electrique,
    calcul_couple_moteur
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

def test_calcul_puissance_moteur_electrique():
    test_name = "test_calcul_puissance_moteur_electrique"
    logger.info(f"Starting {test_name}")
    try:
        # P_wheel=100kW, eta=0.9, losses=5kW => P_motor = (100+5)/0.9 = 116.66 kW
        res = calcul_puissance_moteur_electrique(100000.0, 0.9, pertes_fixes_w=5000.0)
        assert abs(res - 116666.66666) < 1e-5
        
        # Regen (clamp=True)
        assert calcul_puissance_moteur_electrique(-100000.0, 0.9, clamp_non_negative=True) == 0.0
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_couple_moteur():
    test_name = "test_calcul_couple_moteur"
    logger.info(f"Starting {test_name}")
    try:
        # T_wheel=4000Nm, G=10, eta=0.8 => T_motor = 4000 / (10 * 0.8) = 500 Nm
        res = calcul_couple_moteur(4000.0, 10.0, 0.8)
        assert res == 500.0
        
        # Avec pertes
        res_p = calcul_couple_moteur(4000.0, 10.0, 0.8, couple_pertes_nm=400.0)
        assert res_p == 550.0
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e