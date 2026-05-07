# backend/tests/modules/batterie/test_calcul_energie_utile.py
import pytest
import os
import logging
from backend.components.batterie.modules.calcul_energie_utile import (
    calcul_energie_utile_cible,
    calcul_energie_utile_trajet,
    calcul_energie_utile_pic,
    choisir_energie_utile_finale
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_batterie.log")
logger = logging.getLogger("test_batterie")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_energie_utile_cible():
    test_name = "test_calcul_energie_utile_cible"
    logger.info(f"Starting {test_name}")
    try:
        # 2h à 50kW avec 90% rendement => 2 * 50 * 0.9 = 90kWh
        assert calcul_energie_utile_cible(2.0, 50.0, 0.9) == 90.0
        assert calcul_energie_utile_cible(0.0, 50.0, 0.9) == 0.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_energie_utile_trajet():
    test_name = "test_calcul_energie_utile_trajet"
    logger.info(f"Starting {test_name}")
    try:
        # 500km à 0.2kWh/km => 100kWh
        assert calcul_energie_utile_trajet(500.0, 0.2) == 100.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_energie_utile_pic():
    test_name = "test_calcul_energie_utile_pic"
    logger.info(f"Starting {test_name}")
    try:
        # 360kW pendant 10s => 360 * 10 / 3600 = 1kWh
        assert calcul_energie_utile_pic(360.0, 10.0) == 1.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_choisir_energie_utile_finale():
    test_name = "test_choisir_energie_utile_finale"
    logger.info(f"Starting {test_name}")
    try:
        assert choisir_energie_utile_finale(10.0, 50.0, 30.0) == 50.0
        assert choisir_energie_utile_finale() == 0.0
        with pytest.raises(ValueError):
            choisir_energie_utile_finale(10.0, -5.0)
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e