import unittest
from shse_m_sizing.config import InputParameters, DimensionResults
from shse_m_sizing.thermodynamics import calculate_thermodynamics
from shse_m_sizing.mechanical import dimension_components
from shse_m_sizing.materials import get_material

class TestSHSE(unittest.TestCase):
    def setUp(self):
        self.inputs = InputParameters(
            P_batt_target=10.0,
            N_rpm=3000.0,
            p_me_target_bar=6.0
        )
        
    def test_materials(self):
        m = get_material("S235JR")
        self.assertEqual(m.yield_strength, 235e6)
        m2 = get_material("Unknown")
        self.assertEqual(m2.name, "Acier de Construction S235") # Default
        
    def test_thermodynamics(self):
        res = calculate_thermodynamics(self.inputs)
        # Check P_shaft is calculated
        # 10kW / (0.9*0.95*0.95) ~ 12.31 kW
        expected_p_shaft = 10000.0 / (0.9 * 0.95 * 0.95)
        self.assertAlmostEqual(res.P_shaft_req, expected_p_shaft, places=1)
        self.assertGreater(res.Vd_total, 0)
        
    def test_mechanical_sizing(self):
        res = calculate_thermodynamics(self.inputs)
        res = dimension_components(self.inputs, res)
        
        # Check Bore exists
        self.assertGreater(res.Bore, 0.01) # At least 1cm
        self.assertEqual(res.Bore, res.Stroke) # S/B=1
        
        # Check Detailed Components
        self.assertGreater(res.piston_diameter, 0)
        self.assertGreater(res.pin_diameter, 0)
        self.assertGreater(res.rod_bolt_diameter, 0)
        self.assertGreater(res.web_thickness, 0)
        
    def test_integration(self):
        res = calculate_thermodynamics(self.inputs)
        res = dimension_components(self.inputs, res)
        # Ensure no crash on report generation logic (simulated)
        # Check warnings
        self.assertIsInstance(res.warnings, list)

if __name__ == '__main__':
    unittest.main()
