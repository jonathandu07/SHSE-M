import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.moteur_electrique.calcul_force_resistance_vitesse import calcul_force_resistance_totale
from modules.moteur_electrique.calcul_charge_essieu import calcul_charges_essieux
from modules.moteur_electrique.calcul_puissance_roue import calcul_puissance_roue
from modules.moteur_electrique.calcul_acceleration_max import calcul_acceleration_max

class TestMoteurElectrique(unittest.TestCase):

    def test_resistance(self):
        # m=1000, v=0, alpha=0, CdA=0 -> F=m*g*Crr
        res = calcul_force_resistance_totale(1000, 0, 0, 0.01, 0)
        self.assertAlmostEqual(res['F_totale'], 1000*9.81*0.01, places=1)

    def test_puissance_roue(self):
        self.assertEqual(calcul_puissance_roue(1000, 10), 10000)

    def test_charge_essieu(self):
        # Statique plane: m=1000, L=2, lr=1, lf=1 -> Nf=Nr=mg*0.5
        charges = calcul_charges_essieux(1000, 0, 0, 2, 1, 1, 0.5)
        demi_poids = 1000 * 9.81 * 0.5
        self.assertAlmostEqual(charges['N_avant'], demi_poids, places=1)
        self.assertAlmostEqual(charges['N_arriere'], demi_poids, places=1)

if __name__ == '__main__':
    unittest.main()
