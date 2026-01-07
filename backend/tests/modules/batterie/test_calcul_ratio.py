# backend/tests/modules/batterie/test_calcul_ratio.py
import pytest
import os
import logging
import numpy as np
from backend.modules.batterie.calcul_ratio import (
    Carburant, Vehicule, Environnement, BatteriePack, Thermique,
    calcul_densite_air_sec,
    calcul_forces_traction,
    conso_l_100km_pour_capacite,
    balayage_capacites
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

@pytest.fixture
def sample_data():
    fuel = Carburant("Diesel", 42.7, 0.835)
    veh = Vehicule(1500.0, 0.012, 0.6)
    env = Environnement(rho_air_kg_m3=1.225)
    batt = BatteriePack(0.18, 1.0, 0.8, 0.85)
    therm = Thermique(0.35)
    return fuel, veh, env, batt, therm

def test_calcul_densite_air_sec():
    test_name = "test_calcul_densite_air_sec"
    logger.info(f"Starting {test_name}")
    try:
        # ISA sea level: 101325 Pa, 15°C => 1.225 kg/m3
        res = calcul_densite_air_sec(101325.0, 15.0)
        assert abs(res - 1.225) < 1e-3
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_forces_traction():
    test_name = "test_calcul_forces_traction"
    logger.info(f"Starting {test_name}")
    try:
        # m=1500, Crr=0.012, CdA=0.6, v=27.78m/s (100km/h), rho=1.225
        # Fr = 1500 * 9.81 * 0.012 = 176.58
        # Fa = 0.5 * 1.225 * 0.6 * 27.78^2 = 283.4
        res = calcul_forces_traction(
            masse_totale_kg=1500.0, crr=0.012, pente=0.0,
            rho_air_kg_m3=1.225, cda_m2=0.6, vitesse_ms=27.78
        )
        assert res["f_total_n"] > 400.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_conso_l_100km_pour_capacite(sample_data):
    test_name = "test_conso_l_100km_pour_capacite"
    logger.info(f"Starting {test_name}")
    try:
        fuel, veh, env, batt, therm = sample_data
        # Test avec batterie vide
        res0 = conso_l_100km_pour_capacite(
            capacite_nominale_kwh=0.0, vehicule=veh, env=env,
            batterie=batt, thermique=therm, carburant=fuel,
            vitesse_kmh=100.0, pente=0.0
        )
        assert res0["conso_l_100km"] > 0
        
        # Test avec grosse batterie
        res100 = conso_l_100km_pour_capacite(
            capacite_nominale_kwh=100.0, vehicule=veh, env=env,
            batterie=batt, thermique=therm, carburant=fuel,
            vitesse_kmh=100.0, pente=0.0
        )
        # La conso devrait être plus faible (ou nulle si batterie suffit pour 100km)
        assert res100["conso_l_100km"] < res0["conso_l_100km"]
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_balayage_capacites(sample_data):
    test_name = "test_balayage_capacites"
    logger.info(f"Starting {test_name}")
    try:
        fuel, veh, env, batt, therm = sample_data
        caps = np.array([0.0, 20.0, 40.0, 60.0])
        res = balayage_capacites(
            capacites_kwh=caps, vehicule=veh, env=env,
            batterie=batt, thermique=therm, carburants=[fuel],
            vitesse_kmh=100.0, pente=0.0
        )
        assert "best_kwh_minimax" in res
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e