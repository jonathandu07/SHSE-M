# backend/tests/modules/boite_crabots/test_calcul_dimensionnement_crabot.py
import pytest
import os
import logging
import json
from backend.components.boite_crabots.modules.calcul_dimensionnement_crabot import (
    calcul_couple_transmissible_crabot,
    calcul_pression_contact_crabot
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

def test_calcul_couple_transmissible_crabot():
    test_name = "test_calcul_couple_transmissible_crabot"
    logger.info(f"Starting {test_name}")
    try:
        # Nd=4, p_adm=100MPa, h=0.01, b=0.015, r=0.04
        # T = 4 * 100e6 * (0.01 * 0.015) * 0.04 = 4 * 100e6 * 0.00015 * 0.04 = 400 * 15000 * 0.04 = 2400 Nm
        res = calcul_couple_transmissible_crabot(4, 100e6, 0.01, 0.015, 0.04)
        assert abs(res - 2400.0) < 1e-7
        
        # Avec facteur repartition
        res_k = calcul_couple_transmissible_crabot(4, 100e6, 0.01, 0.015, 0.04, facteur_repartition=0.5)
        assert res_k == pytest.approx(1200.0)
        
        # Avec détails
        res_det = calcul_couple_transmissible_crabot(4, 100e6, 0.01, 0.015, 0.04, return_details=True)
        assert res_det["T_cap"] == pytest.approx(2400.0)
        
        # Log détaillé en JSON
        logger.info("RESULTATS DETAILLES COUPLE CRABOT:")
        logger.info(json.dumps(res_det, indent=2, ensure_ascii=False))
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_pression_contact_crabot():
    test_name = "test_calcul_pression_contact_crabot"
    logger.info(f"Starting {test_name}")
    try:
        # T=2400, Nd=4, h=0.01, b=0.015, r=0.04 => p = 100MPa
        res = calcul_pression_contact_crabot(2400.0, 4, 0.01, 0.015, 0.04)
        assert abs(res - 100e6) < 1.0
        
        # Erreurs
        with pytest.raises(ValueError):
            # h=0 => aire=0
            calcul_pression_contact_crabot(2400.0, 4, 0.0, 0.015, 0.04)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e