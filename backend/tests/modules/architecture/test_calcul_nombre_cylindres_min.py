# backend/tests/modules/architecture/test_calcul_nombre_cylindres_min.py
import pytest
import os
import logging
import math
from backend.components.architechture.modules.calcul_nombre_cylindres_min import (
    calcul_nombre_cylindres_min
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

def test_calcul_nombre_cylindres_min():
    test_name = "test_calcul_nombre_cylindres_min"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: Vtot = 2.0L, Vumax = 0.6L => 2.0/0.6 = 3.33 => 4 cylindres
        # En m3: 2e-3 / 0.6e-3
        assert calcul_nombre_cylindres_min(2.0e-3, 0.6e-3) == 4
        
        # Cas exact: 2.0 / 0.5 = 4
        assert calcul_nombre_cylindres_min(2.0e-3, 0.5e-3) == 4
        
        # Cylindrée totale nulle
        assert calcul_nombre_cylindres_min(0.0, 0.5e-3) == 0
        
        # Comportement sentinelle V_u_max <= 0
        assert calcul_nombre_cylindres_min(2.0e-3, 0.0) == 999
        assert calcul_nombre_cylindres_min(2.0e-3, -0.1) == 999
        assert calcul_nombre_cylindres_min(2.0e-3, float('nan')) == 999
        
        # Erreur cylindrée totale négative
        with pytest.raises(ValueError):
            calcul_nombre_cylindres_min(-1.0, 0.5)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e