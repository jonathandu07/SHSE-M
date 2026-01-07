# backend/tests/modules/moteur_thermique/test_calcul_cylindree.py
import pytest
import os
import logging
import math
import json
from backend.modules.moteur_thermique.calcul_cylindree import (
    calcul_cylindree_unitaire,
    calcul_cylindree_totale,
    calcul_volume_mort,
    calcul_taux_compression,
    calcul_ratio_alesage_course,
    calcul_force_gaz,
    calcul_epaisseur_cylindre_mince,
    calcul_epaisseur_cylindre_lame,
    calculer_cylindre_complet
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

def test_calcul_cylindree_unitaire():
    test_name = "test_calcul_cylindree_unitaire"
    logger.info(f"Starting {test_name}")
    try:
        # B=0.08, S=0.08 => Vd = pi * 0.08^2 / 4 * 0.08 = 0.000402 m3 = 402 cm3
        res = calcul_cylindree_unitaire(0.08, 0.08)
        assert abs(res - 0.000402123) < 1e-9
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_cylindree_totale():
    test_name = "test_calcul_cylindree_totale"
    logger.info(f"Starting {test_name}")
    try:
        assert calcul_cylindree_totale(0.0005, 4) == 0.002
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_volume_mort():
    test_name = "test_calcul_volume_mort"
    logger.info(f"Starting {test_name}")
    try:
        # Vd=500cm3, CR=11 => Vc = 500 / 10 = 50cm3
        assert calcul_volume_mort(500.0, 11.0) == 50.0
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calcul_epaisseur_cylindre_mince():
    test_name = "test_calcul_epaisseur_cylindre_mince"
    logger.info(f"Starting {test_name}")
    try:
        # p=10MPa, ri=40mm, sigma_adm=200MPa, FS=2 => sigma_eff=100MPa
        # t = 10 * 40 / 100 = 4 mm
        res = calcul_epaisseur_cylindre_mince(10e6, 0.04, 200e6, facteur_securite=2.0)
        assert abs(res - 0.004) < 1e-9
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_calculer_cylindre_complet():
    test_name = "test_calculer_cylindre_complet"
    logger.info(f"Starting {test_name}")
    try:
        res = calculer_cylindre_complet(alesage_m=0.08, course_m=0.08, nombre_cylindres=4, taux_compression=11.0)
        assert res["cylindree_totale_l"] > 1.6 and res["cylindree_totale_l"] < 1.61
        assert "volume_mort_m3" in res
        
        # Log détaillé en JSON
        logger.info("RESULTATS DETAILLES CYLINDREE:")
        logger.info(json.dumps(res, indent=2, ensure_ascii=False))
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e