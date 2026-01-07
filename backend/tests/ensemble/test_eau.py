import logging
import os
import pytest
import math
from backend.ensemble.eau import (
    pression_hydrostatique,
    profondeur_depuis_pression,
    reynolds,
    etat_eau_pure,
    etat_eau_salee,
    etat_antigel,
    temperature_saturation_eau,
    pression_saturation_eau,
    backends_disponibles,
    P_ATM_STD, G0
)

# Configuration du logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "test_eau.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding="utf-8"
)
logger = logging.getLogger("test_eau")

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_hydrostatics():
    logger.info("Starting test_hydrostatics")
    try:
        rho = 1000.0
        p = pression_hydrostatique(10.0, rho)
        assert abs(p - (P_ATM_STD + 10 * rho * G0)) < 1e-3
        
        z = profondeur_depuis_pression(p, rho)
        assert abs(z - 10.0) < 1e-6
        
        log_test_result("test_hydrostatics", "SUCCESS")
    except Exception as e:
        log_test_result("test_hydrostatics", "FAILED", str(e))
        raise

def test_reynolds_water():
    logger.info("Starting test_reynolds_water")
    try:
        re = reynolds(1000.0, 1.0, 0.1, 1e-3)
        assert abs(re - 100000.0) < 1e-3
        
        log_test_result("test_reynolds_water", "SUCCESS")
    except Exception as e:
        log_test_result("test_reynolds_water", "FAILED", str(e))
        raise

def test_eau_pure():
    logger.info("Starting test_eau_pure")
    try:
        # On vérifie d'abord si un backend est dispo
        b = backends_disponibles()
        if not b.coolprop and not b.iapws:
            logger.warning("No backend for pure water testing. Skipping detailed checks.")
            pytest.skip("No backend for pure water")
            
        state = etat_eau_pure(298.15, P_ATM_STD)
        assert state.rho_kg_m3 > 900.0
        assert state.cp_J_kg_K > 4000.0
        
        log_test_result("test_eau_pure", "SUCCESS")
    except pytest.skip.Exception:
        log_test_result("test_eau_pure", "SKIPPED", "No backend")
    except Exception as e:
        log_test_result("test_eau_pure", "FAILED", str(e))
        raise

def test_eau_salee():
    logger.info("Starting test_eau_salee")
    try:
        b = backends_disponibles()
        if not b.gsw and not b.coolprop:
            pytest.skip("No backend for salt water")
            
        state = etat_eau_salee(298.15, P_ATM_STD, salinite_g_kg=35.0)
        assert state.rho_kg_m3 > 1000.0
        
        log_test_result("test_eau_salee", "SUCCESS")
    except pytest.skip.Exception:
        log_test_result("test_eau_salee", "SKIPPED", "No backend")
    except Exception as e:
        log_test_result("test_eau_salee", "FAILED", str(e))
        raise

def test_antigel():
    logger.info("Starting test_antigel")
    try:
        b = backends_disponibles()
        if not b.coolprop:
            pytest.skip("Antifreeze requires CoolProp")
            
        state = etat_antigel(273.15, P_ATM_STD, fraction_massique_glycol=0.3, type_glycol="MEG")
        assert state.rho_kg_m3 > 1000.0
        
        log_test_result("test_antigel", "SUCCESS")
    except pytest.skip.Exception:
        log_test_result("test_antigel", "SKIPPED", "No CoolProp")
    except Exception as e:
        log_test_result("test_antigel", "FAILED", str(e))
        raise

def test_saturation():
    logger.info("Starting test_saturation")
    try:
        b = backends_disponibles()
        if not b.coolprop and not b.iapws:
            pytest.skip("Saturation requires CoolProp or iapws")
            
        t_sat = temperature_saturation_eau(P_ATM_STD)
        assert abs(t_sat - 373.15) < 1.0 # ~100°C
        
        p_sat = pression_saturation_eau(373.15)
        assert abs(p_sat - P_ATM_STD) < 2000.0
        
        log_test_result("test_saturation", "SUCCESS")
    except pytest.skip.Exception:
        log_test_result("test_saturation", "SKIPPED", "No backend")
    except Exception as e:
        log_test_result("test_saturation", "FAILED", str(e))
        raise

if __name__ == "__main__":
    pytest.main([__file__])