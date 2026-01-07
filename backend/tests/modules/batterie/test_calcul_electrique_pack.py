# backend/tests/modules/batterie/test_calcul_electrique_pack.py
import pytest
import os
import logging
from backend.modules.batterie.calcul_electrique_pack import (
    calcul_conso_kwh_km_depuis_puissance_vitesse,
    calcul_ah_depuis_kwh_tension,
    calcul_courant_depuis_kw_tension,
    calcul_c_rate_depuis_kw_kwh,
    calcul_puissance_effective_stockee,
    calcul_puissance_charge_requise
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

def test_calcul_conso_kwh_km_depuis_puissance_vitesse():
    test_name = "test_calcul_conso_kwh_km_depuis_puissance_vitesse"
    logger.info(f"Starting {test_name}")
    try:
        # 10kW à 50km/h => 0.2 kWh/km
        assert calcul_conso_kwh_km_depuis_puissance_vitesse(10.0, 50.0) == 0.2
        assert calcul_conso_kwh_km_depuis_puissance_vitesse(0.0, 50.0) == 0.0
        with pytest.raises(ValueError):
            calcul_conso_kwh_km_depuis_puissance_vitesse(10.0, 0.0)
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_ah_depuis_kwh_tension():
    test_name = "test_calcul_ah_depuis_kwh_tension"
    logger.info(f"Starting {test_name}")
    try:
        # 40kWh à 400V => 40000 / 400 = 100Ah
        assert calcul_ah_depuis_kwh_tension(40.0, 400.0) == 100.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_courant_depuis_kw_tension():
    test_name = "test_calcul_courant_depuis_kw_tension"
    logger.info(f"Starting {test_name}")
    try:
        # 80kW à 400V => 80000 / 400 = 200A
        assert calcul_courant_depuis_kw_tension(80.0, 400.0) == 200.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_c_rate_depuis_kw_kwh():
    test_name = "test_calcul_c_rate_depuis_kw_kwh"
    logger.info(f"Starting {test_name}")
    try:
        # 100kW sur batterie 50kWh => 2C
        assert calcul_c_rate_depuis_kw_kwh(100.0, 50.0) == 2.0
        with pytest.raises(ValueError):
            calcul_c_rate_depuis_kw_kwh(100.0, 0.0)
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_puissance_effective_stockee():
    test_name = "test_calcul_puissance_effective_stockee"
    logger.info(f"Starting {test_name}")
    try:
        # 50kW charge, 90% rendement => 45kW stockés
        assert calcul_puissance_effective_stockee(50.0, 0.9) == 45.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_puissance_charge_requise():
    test_name = "test_calcul_puissance_charge_requise"
    logger.info(f"Starting {test_name}")
    try:
        # 30kWh à charger en 2h avec 75% rendement => 30 / (2 * 0.75) = 20kW
        assert calcul_puissance_charge_requise(30.0, 2.0, 0.75) == 20.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e