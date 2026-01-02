import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.batterie.calcul_temps_charge import calcul_temps_charge
from modules.batterie.calcul_energie_utile import calcul_energie_utile_cible, calcul_energie_utile_trajet
from modules.batterie.calcul_dimensionnement_batterie import calcul_capacite_totale_batterie, calcul_poids_batterie

class TestBatterie(unittest.TestCase):

    def test_temps_charge(self):
        # 10 kWh utile, 10 kW charge, eta=1 -> 1h
        self.assertEqual(calcul_temps_charge(10, 10, 1.0), 1.0)
        # 10 kWh, 100 kW, eta=0.9 -> 10 / 90 -> 0.111h
        self.assertAlmostEqual(calcul_temps_charge(10, 100, 0.9), 0.111, places=3)

    def test_dimensionnement(self):
        # Eu=60, w=0.6 -> Eb=100
        eb = calcul_capacite_totale_batterie(60, 0.6)
        self.assertEqual(eb, 100.0)
        
        # Eb=100, rho=0.2 -> m=500
        m = calcul_poids_batterie(100, 0.2)
        self.assertEqual(m, 500.0)

if __name__ == '__main__':
    unittest.main()
