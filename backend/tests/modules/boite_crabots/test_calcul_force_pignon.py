# backend/tests/modules/boite_crabots/test_calcul_force_pignon.py
import pytest
import os
import logging
import math
import json
from backend.components.boite_crabots.modules.calcul_force_pignon import (
    calcul_force_tangentielle,
    calcul_forces_engrenage
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

def test_calcul_force_tangentielle():
    test_name = "test_calcul_force_tangentielle"
    logger.info(f"Starting {test_name}")
    try:
        # T=100Nm, d=0.1m => Ft = 2 * 100 / 0.1 = 2000N
        assert calcul_force_tangentielle(100.0, 0.1) == 2000.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_forces_engrenage():
    test_name = "test_calcul_forces_engrenage"
    logger.info(f"Starting {test_name}")
    try:
        # Ft=2000N, phi=20°, beta=0°
        # Fr = 2000 * tan(20°) / cos(0°) = 2000 * 0.36397 = 727.94 N
        # Fa = 2000 * tan(0°) = 0 N
        res = calcul_forces_engrenage(2000.0, 20.0, 0.0)
        assert abs(res["F_r"] - 727.94) < 1e-2
        assert res["F_a"] == 0.0
        
        # Denture hélicoïdale: beta=30°
        # Fr = 2000 * tan(20°) / cos(30°) = 727.94 / 0.866 = 840.57 N
        # Fa = 2000 * tan(30°) = 2000 * 0.57735 = 1154.7 N
        res_h = calcul_forces_engrenage(2000.0, 20.0, 30.0)
        assert abs(res_h["F_r"] - 840.57) < 0.02
        assert abs(res_h["F_a"] - 1154.7) < 1e-1
        
        # Log détaillé en JSON
        logger.info("RESULTATS DETAILLES FORCES ENGRENAGE:")
        logger.info(json.dumps(res_h, indent=2, ensure_ascii=False))
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e