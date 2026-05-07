# backend/tests/modules/architecture/test_calcul_cylindree_admissible.py
import pytest
import os
import logging
import math
from backend.components.architechture.modules.calcul_cylindree_admissible import (
    calcul_bore_max_admissible,
    calcul_cylindree_unit_max
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_architecture.log")
logger = logging.getLogger("test_architecture")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_bore_max_admissible():
    test_name = "test_calcul_bore_max_admissible"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal
        # Up_max = 10 m/s, n = 3000 tr/min, r = 1.0 => S_max = 30*10/3000 = 0.1m, B_max = 0.1/1.0 = 0.1m
        res = calcul_bore_max_admissible(10.0, 3000.0, 1.0)
        assert abs(res - 0.1) < 1e-7
        
        # Régime nul
        assert calcul_bore_max_admissible(10.0, 0.0, 1.0) == 0.0
        
        # Up_max nul
        assert calcul_bore_max_admissible(0.0, 3000.0, 1.0) == 0.0
        
        # Changement de ratio
        # Up_max = 12, n = 2000, r = 1.2 => S_max = 30*12/2000 = 0.18, B_max = 0.18/1.2 = 0.15
        res = calcul_bore_max_admissible(12.0, 2000.0, 1.2)
        assert abs(res - 0.15) < 1e-7
        
        # Erreurs (valeurs négatives)
        with pytest.raises(ValueError):
            calcul_bore_max_admissible(-1.0, 3000.0, 1.0)
        with pytest.raises(ValueError):
            calcul_bore_max_admissible(10.0, -100.0, 1.0)
        with pytest.raises(ValueError):
            calcul_bore_max_admissible(10.0, 3000.0, -0.5)
        with pytest.raises(ValueError):
            calcul_bore_max_admissible(10.0, 3000.0, 0.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_cylindree_unit_max():
    test_name = "test_calcul_cylindree_unit_max"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: B = 0.1m, r = 1.0 => Vd = (pi/4)*0.1^3 * 1.0 = 0.000785398...
        res = calcul_cylindree_unit_max(0.1, 1.0)
        expected = (math.pi / 4.0) * (0.1 ** 3) * 1.0
        assert abs(res - expected) < 1e-12
        
        # B = 0
        assert calcul_cylindree_unit_max(0.0, 1.0) == 0.0
        
        # Erreurs
        with pytest.raises(ValueError):
            calcul_cylindree_unit_max(-0.1, 1.0)
        with pytest.raises(ValueError):
            calcul_cylindree_unit_max(0.1, 0.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e