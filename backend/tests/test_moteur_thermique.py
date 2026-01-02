import unittest
import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.moteur_thermique.calcul_loi_gaz_parfait import calcul_pression_gaz_parfait
from modules.moteur_thermique.calcul_cylindree import calcul_cylindree_unitaire
from modules.moteur_thermique.calcul_vitesse_piston import calcul_vitesse_moyenne_piston
from modules.moteur_thermique.calcul_force_gaz import calcul_force_gaz
from modules.moteur_thermique.calcul_couple_vilebrequin import calcul_couple_instantane
from modules.moteur_thermique.calcul_epaisseur_paroi_cylindre import calcul_epaisseur_cylindre_mince

class TestMoteurThermique(unittest.TestCase):

    def test_cylindree(self):
        # B=1m, S=1m -> pi/4
        v = calcul_cylindree_unitaire(1, 1)
        self.assertAlmostEqual(v, math.pi/4, places=4)

    def test_vitesse_piston(self):
        # S=0.1, n=3000 -> 2*0.1*50 = 10 m/s
        vp = calcul_vitesse_moyenne_piston(0.1, 3000)
        self.assertEqual(vp, 10.0)

    def test_force_gaz(self):
        # p=100Pa, B=sqrt(4/pi) -> area=1 -> F=100
        # B=1.12838...
        f = calcul_force_gaz(100, 1.128379)
        self.assertAlmostEqual(f, 100, places=1)

    def test_couple(self):
        # F=100, r=0.1, theta=90 -> T=10
        t = calcul_couple_instantane(100, 0.1, 90)
        self.assertAlmostEqual(t, 10.0, places=2)
        
        # theta=0 -> T=0
        t0 = calcul_couple_instantane(100, 0.1, 0)
        self.assertAlmostEqual(t0, 0.0, places=2)

if __name__ == '__main__':
    unittest.main()
