# backend/tests/modules/boite_crabots/test_calcul_contact_dent.py
import pytest
import os
import logging
import math
from backend.components.boite_crabots.modules.calcul_contact_dent import (
    calcul_contrainte_contact_hertz
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

def test_calcul_contrainte_contact_hertz():
    test_name = "test_calcul_contrainte_contact_hertz"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: Ft=1000N, b=0.02m, dm=0.05m, Zh=2000
        # Ft/(b*dm) = 1000 / 0.001 = 1,000,000
        # sqrt = 1000
        # sigma = 2000 * 1000 = 2,000,000 Pa
        res = calcul_contrainte_contact_hertz(1000.0, 0.02, 0.05, 2000.0)
        assert abs(res - 2000000.0) < 1e-7
        
        # Avec détails
        res_dict = calcul_contrainte_contact_hertz(1000.0, 0.02, 0.05, 2000.0, return_details=True)
        assert res_dict["sigma_H"] == 2000000.0
        
        # Erreurs
        with pytest.raises(ValueError):
            # dm <= 0
            calcul_contrainte_contact_hertz(1000.0, 0.02, 0.0, 2000.0)
        with pytest.raises(ValueError):
            # Zh <= 0
            calcul_contrainte_contact_hertz(1000.0, 0.02, 0.05, 0.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e