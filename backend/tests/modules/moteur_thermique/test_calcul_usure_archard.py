# backend/tests/modules/moteur_thermique/test_calcul_usure_archard.py
import pytest
import os
import logging
from backend.modules.moteur_thermique.calcul_usure_archard import (
    calcul_volume_usure_archard,
    calcul_perte_epaisseur
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_moteur_thermique.log")
logger = logging.getLogger("test_moteur_thermique")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_volume_usure_archard():
    test_name = "test_calcul_volume_usure_archard"
    logger.info(f"Starting {test_name}")
    try:
        # k=1e-5, W=1000N, Ls=1000m, H=200MPa=2e8Pa
        # Vw = 1e-5 * (1000 * 1000) / 2e8 = 1e-5 * 1e6 / 2e8 = 10 / 2e8 = 5e-8 m3
        res = calcul_volume_usure_archard(1e-5, 1000.0, 1000.0, 2e8)
        assert abs(res - 5e-8) < 1e-12
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_perte_epaisseur():
    test_name = "test_calcul_perte_epaisseur"
    logger.info(f"Starting {test_name}")
    try:
        # Vw=5e-8m3, A=0.01m2 => dh = 5e-6 m = 5 µm
        assert calcul_perte_epaisseur(5e-8, 0.01) == 5e-6
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
