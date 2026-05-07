# backend/tests/modules/moteur_electrique/test_calcul_multi_domaine.py
import pytest
import os
import logging
import json
from backend.components.moteur_electrique.modules.calcul_multi_domaine import (
    calcul_densite_air_sec,
    calcul_demande_nautique,
    calcul_demande_aerien_rho,
    calcul_demande_ferroviaire_davis,
    generer_rapport_mission
)

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs"))
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOG_FILE = os.path.join(LOG_DIR, "test_moteur_electrique.log")
logger = logging.getLogger("test_moteur_electrique")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_calcul_densite_air_sec():
    test_name = "test_calcul_densite_air_sec"
    logger.info(f"Starting {test_name}")
    try:
        # 101325 Pa, 15°C => 1.225
        res = calcul_densite_air_sec(101325.0, 15.0)
        assert abs(res - 1.225) < 1e-3
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_demande_nautique():
    test_name = "test_calcul_demande_nautique"
    logger.info(f"Starting {test_name}")
    try:
        # v=5, S=10, Cw=0.03, rho=1025, eta_h=0.6, eta_m=0.9
        # F = 0.5 * 1025 * 10 * 0.03 * 25 = 3843.75 N
        # P_arbre = (3843.75 * 5) / 0.6 = 32031 W
        # P_elec = 32031 / 0.9 = 35590 W
        res = calcul_demande_nautique(
            vitesse_ms=5.0, surface_mouillee_m2=10.0, cw_coque=0.03,
            rho_eau_kg_m3=1025.0, eta_helice=0.6, eta_moteur=0.9
        )
        assert abs(res["force_N"] - 3843.75) < 1e-7
        assert abs(res["puissance_elec_W"] - 35590.27) < 1.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_generer_rapport_mission():
    test_name = "test_generer_rapport_mission"
    logger.info(f"Starting {test_name}")
    try:
        params = {
            "vitesse_ms": 15.0,
            "rho_air_kg_m3": 1.2,
            "s_cx_cellule_m2": 0.2,
            "eta_helice": 0.8,
            "eta_moteur": 0.9
        }
        res = generer_rapport_mission("aerien", params, tension_systeme_v=400.0)
        assert "courant_estime_A" in res
        assert res["courant_estime_A"] > 0
        
        # Log détaillé en JSON
        logger.info("RESULTATS DETAILLES RAPPORT MISSION:")
        logger.info(json.dumps(res, indent=2, ensure_ascii=False))
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e