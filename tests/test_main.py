import unittest
import os
from shse_m_sizing.config import InputParameters, DimensionResults
from shse_m_sizing.thermodynamics import calculate_thermodynamics
from shse_m_sizing.mechanical import dimension_components
from shse_m_sizing.materials import get_material
from shse_m_sizing.check import verify_constraints
from shse_m_sizing.report import generate_markdown_report, generate_bom_csv, generate_json_export

class TestSHSE(unittest.TestCase):
    def setUp(self):
        self.inputs = InputParameters(
            P_batt_target=10.0,
            N_rpm=3000.0,
            p_me_target_bar=6.0
        )
        # Ensure 'limits' with materials is set (uses defaults)
        
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
        
        # Verify check.py (This triggered the AttributeError before fix)
        res = verify_constraints(self.inputs, res)
        self.assertIsInstance(res.warnings, list)
        
        # Verify report.py (dry run)
        try:
            generate_markdown_report(self.inputs, res, "test_report.md")
            generate_bom_csv(res, "test_bom.csv")
            generate_json_export(self.inputs, res, "test_params.json")
        except AttributeError as e:
            self.fail(f"Report generation raised AttributeError: {e}")
        finally:
            # Cleanup
            if os.path.exists("test_report.md"): os.remove("test_report.md")
            if os.path.exists("test_bom.csv"): os.remove("test_bom.csv")
            if os.path.exists("test_params.json"): os.remove("test_params.json")

if __name__ == '__main__':
    unittest.main()
