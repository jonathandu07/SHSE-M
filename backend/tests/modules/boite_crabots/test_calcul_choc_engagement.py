# backend/tests/modules/boite_crabots/test_calcul_choc_engagement.py
import pytest
import os
import logging
from backend.modules.boite_crabots.calcul_choc_engagement import (
    calcul_inertie_equivalente,
    calcul_energie_choc,
    calcul_couple_synchronisation_moyen
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

def test_calcul_inertie_equivalente():
    test_name = "test_calcul_inertie_equivalente"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal: J1=0.1, J2=0.1 => Jeq = 0.01 / 0.2 = 0.05
        assert calcul_inertie_equivalente(0.1, 0.1) == 0.05
        # Cas asymétrique: J1=10, J2=0.1 => Jeq = 1 / 10.1 = 0.099...
        res = calcul_inertie_equivalente(10.0, 0.1)
        assert abs(res - (1.0/10.1)) < 1e-10
        # Cas epsilon
        assert calcul_inertie_equivalente(0.000000000001, -0.000000000001) == 0.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_energie_choc():
    test_name = "test_calcul_energie_choc"
    logger.info(f"Starting {test_name}")
    try:
        # Jeq=0.05, d_omega=100 rad/s => E = 0.5 * 0.05 * 10000 = 250J
        assert calcul_energie_choc(0.05, 100.0) == 250.0
        # Signe d_omega
        assert calcul_energie_choc(0.05, -100.0) == 250.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_couple_synchronisation_moyen():
    test_name = "test_calcul_couple_synchronisation_moyen"
    logger.info(f"Starting {test_name}")
    try:
        # Jeq=0.05, d_omega=100rad/s, t=0.1s => T = 0.05*100/0.1 = 50 Nm
        assert calcul_couple_synchronisation_moyen(0.05, 100.0, 0.1) == 50.0
        # Erreur t=0
        with pytest.raises(ValueError):
            calcul_couple_synchronisation_moyen(0.05, 100.0, 0.0)
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e