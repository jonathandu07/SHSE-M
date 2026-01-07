# backend/tests/modules/architecture/test_resolution_globale_architecture.py
import pytest
import os
import logging
from backend.modules.architecture.resolution_globale_architecture import (
    resoudre_architecture_globale
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

def test_resoudre_architecture_globale():
    test_name = "test_resoudre_architecture_globale"
    logger.info(f"Starting {test_name}")
    try:
        # Cas nominal SHSE-M 150kW
        # n=4500 rpm, PME=12 bar, Up_max=25 m/s, L=1.2, W=0.8
        res = resoudre_architecture_globale(150000.0, 4500.0, 12e5, 25.0, 1.2, 0.8)
        assert isinstance(res, dict)
        if res: # Si une solution est trouvée
            assert "N_cyl" in res
            assert "Architecture" in res
            assert "Score" in res
            assert res["N_cyl"] >= 1
            
        # Cas puissance nulle
        assert resoudre_architecture_globale(0.0, 4500.0, 12e5, 25.0, 1.2, 0.8) == {}
        
        # Cas impossible (contraintes trop fortes)
        # Up_max minuscule => cyl_unit_max minuscule => N_min énorme > 24
        res_imp = resoudre_architecture_globale(500000.0, 6000.0, 10e5, 1.0, 0.5, 0.5)
        assert res_imp == {}
        
        # Erreurs
        with pytest.raises(ValueError):
            resoudre_architecture_globale(-100.0, 4500.0, 12e5, 25.0, 1.2, 0.8)
            
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e