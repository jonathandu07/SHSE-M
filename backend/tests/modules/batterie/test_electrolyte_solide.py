# backend/tests/modules/batterie/test_electrolyte_solide.py
import pytest
import os
import logging
from backend.components.batterie.modules.electrolyte_solide import (
    ElectrolyteSolide, CelluleSolide, PackSolide, Options,
    evaluer_electrolyte_solide
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

def test_evaluer_electrolyte_solide_nominal():
    test_name = "test_evaluer_electrolyte_solide_nominal"
    logger.info(f"Starting {test_name}")
    try:
        elec = ElectrolyteSolide(
            conductivite_ionique_s_m=1.0,
            epaisseur_m=50e-6
        )
        cell = CelluleSolide(
            surface_active_m2=0.01,
            tension_nominale_v=3.7,
            capacite_ah=5.0
        )
        pack = PackSolide(
            nb_series=100,
            nb_parallele=2,
            puissance_continue_kw=37.0 # 37kW sur 370V => 100A pack => 50A par cellule
        )
        
        rep = evaluer_electrolyte_solide(elec, cell, pack)
        
        # R = t / (k*A) = 50e-6 / (1.0 * 0.01) = 0.005 Ohm
        assert abs(rep.resistance_electrolyte_ohm_par_cell - 0.005) < 1e-9
        # I_cell = 50A
        # Losses_cell = 50^2 * 0.005 = 2500 * 0.005 = 12.5 W
        assert abs(rep.pertes_joule_cell_continu_w - 12.5) < 1e-7
        # Total losses = 12.5 * 200 = 2500 W
        assert abs(rep.pertes_joule_pack_continu_w - 2500.0) < 1e-7
        
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e

def test_evaluer_electrolyte_solide_incomple():
    test_name = "test_evaluer_electrolyte_solide_incomple"
    logger.info(f"Starting {test_name}")
    try:
        elec = ElectrolyteSolide(conductivite_ionique_s_m=1.0) # manque epaisseur
        cell = CelluleSolide(surface_active_m2=0.01)
        pack = PackSolide(nb_series=100)
        
        rep = evaluer_electrolyte_solide(elec, cell, pack, Options(strict=False))
        assert "elec.epaisseur_m" in rep.inconnues
        assert rep.resistance_electrolyte_ohm_par_cell is None
        
        with pytest.raises(ValueError):
             evaluer_electrolyte_solide(elec, cell, pack, Options(strict=True))
             
        log_test_result(test_name, "SUCCESS")
    except Exception as e:
        log_test_result(test_name, "FAILED", str(e))
        raise e
