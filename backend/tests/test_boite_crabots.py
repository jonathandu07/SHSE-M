import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.boite_crabots.calcul_force_pignon import calcul_force_tangentielle, calcul_forces_engrenage
from modules.boite_crabots.calcul_flexion_dent import calcul_contrainte_flexion_lewis
from modules.boite_crabots.calcul_duree_vie_roulement import calcul_duree_vie_l10, calcul_duree_vie_heures
from modules.boite_crabots.calcul_choc_engagement import calcul_inertie_equivalente, calcul_energie_choc

class TestBoiteCrabots(unittest.TestCase):

    def test_efforts_engrenage(self):
        # T=100, d=0.1 -> Ft=2000
        ft = calcul_force_tangentielle(100, 0.1)
        self.assertEqual(ft, 2000.0)
        
        # 20 deg, 0 helix -> Fr = 2000 * tan(20) ~ 727.9
        forces = calcul_forces_engrenage(2000, 20, 0)
        self.assertAlmostEqual(forces['F_r'], 727.94, places=1)
        self.assertEqual(forces['F_a'], 0.0)

    def test_roulement(self):
        # C=10000, P=1000, bille -> (10)^3 = 1000 M tours
        l10 = calcul_duree_vie_l10(10000, 1000, 'bille')
        self.assertEqual(l10, 1000.0)

    def test_choc(self):
        J = calcul_inertie_equivalente(1, 1) # -> 0.5
        self.assertEqual(J, 0.5)
        # E = 0.5 * 0.5 * (10^2) = 25
        e = calcul_energie_choc(0.5, 10)
        self.assertEqual(e, 25.0)

if __name__ == '__main__':
    unittest.main()
