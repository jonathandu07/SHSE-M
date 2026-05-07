# backend/tests/modules/architecture/test_calcul_cout_maintenance_archard.py
import pytest
import os
import logging
import math
from unittest.mock import patch, MagicMock
from backend.components.architechture.modules.calcul_cout_maintenance_archard import (
    calcul_cout_maintenance_estime,
    _normaliser_montant_eur,
    _extraire_montants_eur
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

def test_calcul_cout_maintenance_estime():
    test_name = "test_calcul_cout_maintenance_estime"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal
        # T=1000h, L0=5000h, W0=1000N, W=1000N, nb_base=4, nb_actuel=4, cout_base=1000€
        # ratio_charge = 1.0 => duree_vie = 5000 * 1.0^1.5 = 5000
        # nb_inter = 1000 / 5000 = 0.2
        # facteur_joints = 4/4 = 1.0 => cout_par_inter = 1000
        # total = 0.2 * 1000 = 200€
        res = calcul_cout_maintenance_estime(1000.0, 5000.0, 1000.0, 1000.0, 4, 4, 1000.0)
        assert abs(res - 200.0) < 1e-7
        
        # Charge double
        # W=2000N => ratio=0.5 => vie = 5000 * 0.5^1.5 = 5000 * 0.35355 = 1767.76
        # nb_inter = 1000 / 1767.76 = 0.56568
        # total = 0.56568 * 1000 = 565.68
        res = calcul_cout_maintenance_estime(1000.0, 5000.0, 1000.0, 2000.0, 4, 4, 1000.0)
        expected = 1000.0 * (1000.0 / (5000.0 * (0.5**1.5)))
        assert abs(res - expected) < 1e-7
        
        # Charge nulle
        assert calcul_cout_maintenance_estime(1000.0, 5000.0, 1000.0, 0.0, 4, 4, 1000.0) == 0.0
        
        # Erreurs
        with pytest.raises(ValueError):
            calcul_cout_maintenance_estime(-10.0, 5000.0, 1000.0, 1000.0, 4, 4, 1000.0)
        with pytest.raises(ValueError):
            calcul_cout_maintenance_estime(1000.0, 0.0, 1000.0, 1000.0, 4, 4, 1000.0)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_normalisation_prix():
    test_name = "test_normalisation_prix"
    logger.info(f"Starting {test_name}")
    try:
        assert _normaliser_montant_eur("1 234,56") == 1234.56
        assert _normaliser_montant_eur("1234.56") == 1234.56
        assert _normaliser_montant_eur("abc") is None
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_extraction_prix():
    test_name = "test_extraction_prix"
    logger.info(f"Starting {test_name}")
    try:
        html = "Le prix est de 12,50 € et l'autre de 100 EUR."
        res = _extraire_montants_eur(html)
        assert 12.5 in res
        assert 100.0 in res
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e