# backend/tests/modules/moteur_thermique/test_calcul_gaz.py
import pytest
import os
import logging
import math
from backend.modules.moteur_thermique.calcul_gaz import (
    calcul_pression_gaz_parfait,
    calcul_masse_gaz_parfait,
    calcul_temperature_compression_adiabatique,
    calcul_debit_fuite_annulaire,
    calculer_gaz_complet
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

def test_calcul_pression_gaz_parfait():
    test_name = "test_calcul_pression_gaz_parfait"
    logger.info(f"Starting {test_name}")
    try:
        # m=0.001kg, V=0.001m3, T=300K, R=287.05 (default) => P = 0.001 * 287.05 * 300 / 0.001 = 86115.0 Pa
        assert calcul_pression_gaz_parfait(0.001, 0.001, 300.0) == pytest.approx(86115.0)
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_temperature_compression_adiabatique():
    test_name = "test_calcul_temperature_compression_adiabatique"
    logger.info(f"Starting {test_name}")
    try:
        # T1=300K, P1=1bar, P2=10bar, gamma=1.4 => T2 = 300 * 10^(0.4/1.4) = 300 * 10^0.2857 = 300 * 1.93 = 579 K
        res = calcul_temperature_compression_adiabatique(300.0, 1e5, 10e5)
        assert abs(res - 579.2) < 1.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_debit_fuite_annulaire():
    test_name = "test_calcul_debit_fuite_annulaire"
    logger.info(f"Starting {test_name}")
    try:
        # dP=10MPa, h=50µm, r=40mm, L=10mm, mu=0.01Pa.s
        # Q = (pi * 0.04 * (50e-6)^3 * 10e6) / (6 * 0.01 * 0.01) = (pi * 0.04 * 1.25e-13 * 10e6) / 0.0006 = 0.000157 / 0.0006 = 0.26 m3/s (environ)
        # Attends, recalcul: Q = (pi * 0.04 * 1.25e-13 * 10e6) / (6 * 6.01 * 0.01) = 1.57e-7 / 6e-4 = 0.0002618 m3/s
        res = calcul_debit_fuite_annulaire(10e6, 50e-6, 0.04, 0.01, 0.01)
        assert abs(res - 0.0002618) < 1e-6
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
