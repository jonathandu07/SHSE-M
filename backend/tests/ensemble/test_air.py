import logging
import os
import pytest
import math
from backend.ensemble.air import (
    dry_air_mole_fractions,
    mixture_molar_mass_from_mole_fractions,
    oxygen_mass_fraction_in_dry_air,
    geometric_to_geopotential,
    geopotential_to_geometric,
    isa_dry_temperature_pressure,
    isa_density,
    saturation_vapor_pressure_Pa_Tetens,
    vapor_pressure_from_RH,
    humidity_ratio_w,
    specific_humidity_q,
    dew_point_C_from_vapor_pressure_Tetens,
    dynamic_viscosity_air_Pa_s,
    cp_dry_air_J_kgK,
    gamma_from_cp_R,
    speed_of_sound_m_s,
    thermal_conductivity_W_mK,
    air_state,
    altitude_from_pressure_ISA,
    M_WV, R_DRY, GAMMA_DRY, P0, T0
)

# Configuration du logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "test_air.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding="utf-8"
)
logger = logging.getLogger("test_air")

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_composition():
    logger.info("Starting test_composition")
    try:
        # Test dry_air_mole_fractions
        y = dry_air_mole_fractions(co2_ppm=420.0)
        assert abs(sum(y.values()) - 1.0) < 1e-9
        assert abs(y["CO2"] - 0.00042) < 1e-9
        
        # Test mixture_molar_mass_from_mole_fractions
        m_mix = mixture_molar_mass_from_mole_fractions(y)
        assert 0.028 < m_mix < 0.030
        
        # Test oxygen_mass_fraction_in_dry_air
        o2_frac = oxygen_mass_fraction_in_dry_air(co2_ppm=420.0)
        assert 0.23 < o2_frac < 0.24
        
        log_test_result("test_composition", "SUCCESS")
    except Exception as e:
        log_test_result("test_composition", "FAILED", str(e))
        raise

def test_altitude_conversions():
    logger.info("Starting test_altitude_conversions")
    try:
        h = 10000.0
        H = geometric_to_geopotential(h)
        h_back = geopotential_to_geometric(H)
        assert abs(h - h_back) < 1e-6
        
        with pytest.raises(ValueError):
            geometric_to_geopotential(-1000.0)
            
        log_test_result("test_altitude_conversions", "SUCCESS")
    except Exception as e:
        log_test_result("test_altitude_conversions", "FAILED", str(e))
        raise

def test_isa_model():
    logger.info("Starting test_isa_model")
    try:
        # Niveau mer
        T, p = isa_dry_temperature_pressure(0.0)
        assert abs(T - T0) < 1e-3
        assert abs(p - P0) < 1e-3
        
        # 11km (tropopause)
        T11, p11 = isa_dry_temperature_pressure(11000.0)
        assert abs(T11 - 216.65) < 0.1
        
        # Densité
        rho = isa_density(P0, T0)
        assert abs(rho - 1.225) < 0.01
        
        log_test_result("test_isa_model", "SUCCESS")
    except Exception as e:
        log_test_result("test_isa_model", "FAILED", str(e))
        raise

def test_humidity():
    logger.info("Starting test_humidity")
    try:
        T_C = 25.0
        p_sat = saturation_vapor_pressure_Pa_Tetens(T_C)
        assert 3100 < p_sat < 3200
        
        RH = 0.5
        e = vapor_pressure_from_RH(P0, T_C, RH)
        assert abs(e - (0.5 * p_sat)) < 1e-3
        
        w = humidity_ratio_w(P0, e)
        assert 0.009 < w < 0.011
        
        q = specific_humidity_q(P0, e)
        assert abs(q - (w / (1 + w))) < 1e-9
        
        td = dew_point_C_from_vapor_pressure_Tetens(e)
        assert abs(td - 13.9) < 0.5
        
        log_test_result("test_humidity", "SUCCESS")
    except Exception as e:
        log_test_result("test_humidity", "FAILED", str(e))
        raise

def test_fluid_properties():
    logger.info("Starting test_fluid_properties")
    try:
        # Viscosité (T=15°C)
        mu = dynamic_viscosity_air_Pa_s(T0)
        assert abs(mu - 1.789e-5) < 1e-7
        
        # Cp
        cp = cp_dry_air_J_kgK(gamma=1.4, R_spec=287.053)
        assert abs(cp - 1004.7) < 0.5
        
        # Gamma
        gamma = gamma_from_cp_R(1005.0, 287.0)
        assert abs(gamma - 1.4) < 0.01
        
        # Son
        a = speed_of_sound_m_s(T0, 1.4, 287.05)
        assert abs(a - 340.3) < 0.5
        
        # Conductivité
        k = thermal_conductivity_W_mK(mu, cp, Pr=0.71)
        assert 0.024 < k < 0.026
        
        log_test_result("test_fluid_properties", "SUCCESS")
    except Exception as e:
        log_test_result("test_fluid_properties", "FAILED", str(e))
        raise

def test_air_state():
    logger.info("Starting test_air_state")
    try:
        state = air_state(altitude_m=0.0, temperature_offset_K=0.0, RH=0.0)
        assert abs(state.T_K - T0) < 1e-3
        assert abs(state.p_Pa - P0) < 1e-3
        
        # Mach
        m = state.mach(100.0)
        assert abs(m - (100.0 / state.a_m_s)) < 1e-6
        
        # Reynolds
        re = state.reynolds(v_m_s=50.0, L_m=1.0)
        assert re > 0
        
        log_test_result("test_air_state", "SUCCESS")
    except Exception as e:
        log_test_result("test_air_state", "FAILED", str(e))
        raise

def test_inversions():
    logger.info("Starting test_inversions")
    try:
        # Retrouver altitude depuis pression
        target_p = 70108.0 # ~3000m
        alt = altitude_from_pressure_ISA(target_p)
        assert abs(alt - 3000.0) < 10.0
        
        log_test_result("test_inversions", "SUCCESS")
    except Exception as e:
        log_test_result("test_inversions", "FAILED", str(e))
        raise

if __name__ == "__main__":
    pytest.main([__file__])