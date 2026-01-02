import unittest
import sys
import os

# Ajout du chemin racine pour import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.alternateur.calcul_vitesse_angulaire import calcul_vitesse_angulaire
from modules.alternateur.calcul_couple_alternateur import calcul_couple_alternateur
from modules.alternateur.calcul_puissance_mecanique import calcul_puissance_mecanique
from modules.alternateur.calcul_frequence_synchrone import calcul_frequence_synchrone
from modules.alternateur.calcul_puissance_electrique import calcul_puissance_triphase
from modules.alternateur.calcul_fem_induite import calcul_fem_induite
from modules.alternateur.calcul_pertes_cuivre import calcul_pertes_cuivre_triphase
from modules.alternateur.calcul_pertes_fer import calcul_pertes_fer_steinmetz
from modules.alternateur.calcul_rendement_alternateur import calcul_rendement_alternateur

class TestAlternateur(unittest.TestCase):
    
    def test_vitesse_angulaire(self):
        # 3000 tr/min -> ~314.16 rad/s
        self.assertAlmostEqual(calcul_vitesse_angulaire(3000), 314.159, places=2)
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(-100)

    def test_couple_et_puissance(self):
        # Pe=10kW, eta=0.9 -> Pmec=11.11kW
        pmec = calcul_puissance_mecanique(10000, 0.9)
        self.assertAlmostEqual(pmec, 11111.11, places=1)
        
        # Omega=100 -> T = 111.11 Nm
        couple = calcul_couple_alternateur(10000, 0.9, 100)
        self.assertAlmostEqual(couple, 111.11, places=1)

    def test_frequence(self):
        # 3000 tr/min, 2 pôles -> 50 Hz
        f = calcul_frequence_synchrone(3000, 2)
        self.assertEqual(f, 50.0)

    def test_electrique(self):
        # 400V, 10A -> 6928 W
        p = calcul_puissance_triphase(400, 10, 1.0)
        self.assertAlmostEqual(p, 6928.2, places=1)

if __name__ == '__main__':
    unittest.main()
