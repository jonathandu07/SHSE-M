# backend/tests/modules/boite_crabots/test_calcul_dimensionnement_arbre.py
import pytest
import os
import logging
import math
import json
from backend.modules.boite_crabots.calcul_dimensionnement_arbre import (
    calcul_contrainte_cisaillement_torsion,
    calcul_contrainte_flexion_arbre,
    calcul_von_mises_arbre,
    calcul_coefficient_securite,
    calcul_angle_torsion,
    estimer_diametre_minimal_von_mises
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

def test_calcul_contrainte_cisaillement_torsion():
    test_name = "test_calcul_contrainte_cisaillement_torsion"
    logger.info(f"Starting {test_name}")
    try:
        # T=1000Nm, d=0.05m => tau = 16*1000 / (pi * 0.05^3) = 16000 / (pi * 0.000125) = 16000 / 0.0003927 = 40.74 MPa
        res = calcul_contrainte_cisaillement_torsion(1000.0, 0.05)
        expected = (16.0 * 1000.0) / (math.pi * (0.05**3))
        assert abs(res - expected) < 1e-1
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_contrainte_flexion_arbre():
    test_name = "test_calcul_contrainte_flexion_arbre"
    logger.info(f"Starting {test_name}")
    try:
        # M=1000Nm, d=0.05m => sigma = 32*1000 / (pi * 0.05^3) = 2 * tau = 81.48 MPa
        res = calcul_contrainte_flexion_arbre(1000.0, 0.05)
        expected = (32.0 * 1000.0) / (math.pi * (0.05**3))
        assert abs(res - expected) < 1e-1
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_von_mises_arbre():
    test_name = "test_calcul_von_mises_arbre"
    logger.info(f"Starting {test_name}")
    try:
        # sigma=100MPa, tau=50MPa => sqrt(100^2 + 3*50^2) = sqrt(10000 + 7500) = sqrt(17500) = 132.28 MPa
        res = calcul_von_mises_arbre(100e6, 50e6)
        assert abs(res - 132287565.5) < 1.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_coefficient_securite():
    test_name = "test_calcul_coefficient_securite"
    logger.info(f"Starting {test_name}")
    try:
        assert calcul_coefficient_securite(200e6, 400e6) == 2.0
        assert calcul_coefficient_securite(0.0, 400e6) == float("inf")
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_angle_torsion():
    test_name = "test_calcul_angle_torsion"
    logger.info(f"Starting {test_name}")
    try:
        # T=1000, L=1.0, d=0.05, G=80e9
        res = calcul_angle_torsion(1000.0, 1.0, 0.05, 80e9)
        expected = (32.0 * 1000.0 * 1.0) / (math.pi * 80e9 * (0.05**4))
        assert abs(res - expected) < 1e-9
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_estimer_diametre_minimal_von_mises():
    test_name = "test_estimer_diametre_minimal_von_mises"
    logger.info(f"Starting {test_name}")
    try:
        # T=1000, M=500, Re=300MPa, S=2.0
        res = estimer_diametre_minimal_von_mises(1000.0, 500.0, 300e6, 2.0)
        assert res > 0.01 and res < 0.1
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_details_arbre():
    test_name = "test_calcul_details_arbre"
    logger.info(f"Starting {test_name}")
    try:
        # Synthèse manuelle pour le log détaillé
        synthese = {
            "diametre_mini": estimer_diametre_minimal_von_mises(1000.0, 500.0, 300e6, 2.0),
            "unite": "m"
        }
        logger.info("RESULTATS DETAILLES SYNTHESE ARBRE:")
        logger.info(json.dumps(synthese, indent=2, ensure_ascii=False))
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e