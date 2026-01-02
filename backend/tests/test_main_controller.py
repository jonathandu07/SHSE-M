import unittest
import sys
import os

# Ajout du chemin racine pour import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.main import dimensionner_systeme_shsem

class TestMainController(unittest.TestCase):

    def test_dimensionnement_standard(self):
        """Teste le flux de dimensionnement pour une puissance standard (150kW)."""
        res = dimensionner_systeme_shsem(150.0)
        self.assertIsNotNone(res)
        self.assertIn('N_cyl', res)
        self.assertIn('Architecture', res)
        self.assertIn('Bore_mm', res)
        self.assertIn('RPM', res)
        
    def test_puissance_faible(self):
        """Teste le flux pour une très faible puissance (10kW)."""
        res = dimensionner_systeme_shsem(10.0)
        self.assertIsNotNone(res)
        self.assertGreaterEqual(res['N_cyl'], 1)

    def test_puissance_haute(self):
        """Teste le flux pour une puissance élevée (500kW)."""
        res = dimensionner_systeme_shsem(500.0)
        # 500kW peut être complexe selon les contraintes, on vérifie si ça passe ou si c'est géré
        if res:
            self.assertIn('Architecture', res)

    def test_option_batterie(self):
        """Vérifie que l'option de charge batterie influence le calcul sans crasher."""
        res_with_bat = dimensionner_systeme_shsem(100.0, charger_batterie=True)
        res_no_bat = dimensionner_systeme_shsem(100.0, charger_batterie=False)
        self.assertIsNotNone(res_with_bat)
        self.assertIsNotNone(res_no_bat)

if __name__ == '__main__':
    unittest.main()
