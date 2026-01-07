# backend/tests/modules/architecture/test_choix_architecture_optimale.py
import pytest
import os
import logging
from backend.modules.architecture.choix_architecture_optimale import (
    evaluer_architecture,
    choix_architecture_optimale
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

def test_evaluer_architecture():
    test_name = "test_evaluer_architecture"
    logger.info(f"Starting {test_name}")
    try:
        # Architecture en ligne (L), 4 cylindres, dispos 1m x 1m
        # L_pkg = 4 * 0.15 = 0.6m, W_pkg = 0.4m => Valide
        score, valide = evaluer_architecture("L", 4, 1.0, 1.0)
        assert valide is True
        assert score < 1000.0
        
        # Architecture V, 4 cylindres, dispos 1m x 1m
        # L_pkg = 0.5 * (4 * 0.15) = 0.3m, W_pkg = 0.4 * 1.5 = 0.6m => Valide
        score_v, valide_v = evaluer_architecture("V", 4, 1.0, 1.0)
        assert valide_v is True
        
        # Trop long pour dispo
        score_too_long, valide_too_long = evaluer_architecture("L", 20, 1.0, 1.0)
        assert valide_too_long is False
        assert score_too_long > 1000.0
        
        # Architecture impossible (V pour 3 cylindres)
        score_imp, valide_imp = evaluer_architecture("V", 3, 1.0, 1.0)
        assert valide_imp is False
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_choix_architecture_optimale():
    test_name = "test_choix_architecture_optimale"
    logger.info(f"Starting {test_name}")
    try:
        # N=4, L_max=1.0, W_max=1.0 => L ou V possible. L est plus simple (score complexité 1.0 vs 1.3)
        res = choix_architecture_optimale(4, 1.0, 1.0)
        assert res == "L"
        
        # N=12, L_max=1.0, W_max=1.0
        # L: L_pkg = 12 * 0.15 = 1.8m > 1.0 => Invalide
        # V: L_pkg = 6 * 0.15 = 0.9m < 1.0, W_pkg = 0.6m < 1.0 => Valide
        res_large = choix_architecture_optimale(12, 1.0, 1.0)
        assert res_large == "V"
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e