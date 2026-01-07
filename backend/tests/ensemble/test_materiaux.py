import logging
import os
import pytest
import math
from backend.ensemble.materiaux import (
    Intervalle,
    valeur,
    get_materiau,
    lister_materiaux,
    MATERIAUX,
    MPA, GPA
)

# Configuration du logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "test_materiaux.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding="utf-8"
)
logger = logging.getLogger("test_materiaux")

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_intervalle():
    logger.info("Starting test_intervalle")
    try:
        inv = Intervalle(100.0, 200.0)
        assert inv.typique() == 150.0
        inv.verifier()
        
        with pytest.raises(ValueError):
            Intervalle(200.0, 100.0).verifier()
            
        assert valeur(inv, mode="min") == 100.0
        assert valeur(inv, mode="max") == 200.0
        assert valeur(inv, mode="typique") == 150.0
        assert valeur(123.4) == 123.4
        
        log_test_result("test_intervalle", "SUCCESS")
    except Exception as e:
        log_test_result("test_intervalle", "FAILED", str(e))
        raise

def test_materiau_lookup():
    logger.info("Starting test_materiau_lookup")
    try:
        m = get_materiau("alu_6061_t6")
        assert m.cle == "alu_6061_t6"
        assert "Aluminium" in m.nom
        
        with pytest.raises(KeyError):
            get_materiau("materiau_inexistant")
            
        mats = lister_materiaux(famille="metal")
        assert len(mats) > 0
        assert all(m.famille == "metal" for m in mats)
        
        log_test_result("test_materiau_lookup", "SUCCESS")
    except Exception as e:
        log_test_result("test_materiau_lookup", "FAILED", str(e))
        raise

def test_rdm_properties():
    logger.info("Starting test_rdm_properties")
    try:
        m = get_materiau("alu_6061_t6")
        
        # G = E / (2*(1+nu))
        G = m.module_cisaillement_pa()
        assert G is not None
        assert 25e9 < G < 27e9 # ~26 GPa
        
        # K = E / (3*(1-2*nu))
        K = m.module_compression_pa()
        assert K is not None
        assert K > G
        
        # Masse
        vol = 0.001 # 1 litre
        assert abs(m.masse_kg(vol) - 2.7) < 1e-3
        
        log_test_result("test_rdm_properties", "SUCCESS")
    except Exception as e:
        log_test_result("test_rdm_properties", "FAILED", str(e))
        raise

def test_admissible_stresses():
    logger.info("Starting test_admissible_stresses")
    try:
        m = get_materiau("acier_42crmo4_qt")
        
        # Sigma admissible
        # Rp0.2 min pour 16-40mm est 750 MPa
        sigma_adm = m.sigma_admissible_pa(coef_securite=2.0, section_mm=20.0, critere="elasticite")
        assert abs(sigma_adm - (750.0 * MPA / 2.0)) < 1e-3
        
        # Tau admissible (von mises)
        tau_adm = m.tau_admissible_pa(coef_securite=2.0, section_mm=20.0, hypothese="von_mises")
        expected_tau_y = 750.0 * MPA / math.sqrt(3.0)
        assert abs(tau_adm - (expected_tau_y / 2.0)) < 1e-3
        
        log_test_result("test_admissible_stresses", "SUCCESS")
    except Exception as e:
        log_test_result("test_admissible_stresses", "FAILED", str(e))
        raise

def test_thermique():
    logger.info("Starting test_thermique")
    try:
        m = get_materiau("alu_6061_t6")
        k = valeur(m.conductivite_thermique_w_mk)
        assert abs(k - 167.0) < 1e-3
        
        alpha = valeur(m.alpha_dilatation_1_k)
        assert abs(alpha - 23.6e-6) < 1e-9
        
        log_test_result("test_thermique", "SUCCESS")
    except Exception as e:
        log_test_result("test_thermique", "FAILED", str(e))
        raise

if __name__ == "__main__":
    pytest.main([__file__])