import unittest
import sys
import os

# Ajout du chemin racine pour import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.modules.architecture.calcul_cylindree_totale import calcul_cylindree_totale_requise
from backend.modules.architecture.calcul_cylindree_admissible import calcul_bore_max_admissible, calcul_cylindree_unit_max
from backend.modules.architecture.calcul_nombre_cylindres_min import calcul_nombre_cylindres_min
from backend.modules.architecture.choix_architecture_optimale import choix_architecture_optimale

class TestArchitecture(unittest.TestCase):

    def test_cylindree_totale(self):
        # 100 kW, PME 10 bar, 50 Hz (3000 rpm 4T)
        v_tot = calcul_cylindree_totale_requise(100000, 10e5, 25, 1.0) # f=3000/120=25
        # V = P / (pme * f) = 100000 / (1e6 * 25) = 100000 / 25000000 = 0.004 m3 = 4L
        self.assertAlmostEqual(v_tot, 0.004)

    def test_cylindree_admissible(self):
        # Vitesse piston 20 m/s, 6000 rpm (100 tr/s)
        # S_max = 30 * 20 / 6000 = 600 / 6000 = 0.1 m
        # B_max = S_max / 1.0 = 0.1 m
        b_max = calcul_bore_max_admissible(20, 6000, 1.0)
        self.assertAlmostEqual(b_max, 0.1)

    def test_nombre_cylindres(self):
        # Total 4L, Max Unit 1L -> 4 cyl
        n = calcul_nombre_cylindres_min(0.004, 0.001)
        self.assertEqual(n, 4)
        
    def test_choix_architecture(self):
        # 6 cyl, place limitée en long (0.6m) mais large
        # Ligne: 6*0.15 = 0.9m > 0.6 -> Non
        # V: 3*0.15 = 0.45m < 0.6 -> Oui
        arch = choix_architecture_optimale(6, 0.6, 1.0)
        self.assertEqual(arch, "V")

if __name__ == '__main__':
    unittest.main()
