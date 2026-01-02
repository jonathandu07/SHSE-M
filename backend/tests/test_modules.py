import sys
import os
import unittest

# Ajouter le chemin racine pour l'import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import des modules (quelques exemples représentatifs pour vérifier l'intégrité)
from modules.alternateur.calcul_vitesse_angulaire import calcul_vitesse_angulaire
from modules.batterie.calcul_temps_charge import calcul_temps_charge
from modules.boite_crabots.calcul_force_pignon import calcul_force_tangentielle
from modules.moteur_electrique.calcul_puissance_roue import calcul_puissance_roue
from modules.moteur_thermique.calcul_cylindree import calcul_cylindree_unitaire

class TestFormules(unittest.TestCase):

    def test_alternateur(self):
        # 3000 tr/min -> 314.159 rad/s
        omega = calcul_vitesse_angulaire(3000)
        self.assertAlmostEqual(omega, 314.159, places=1)
        print("Alternateur: OK")

    def test_batterie(self):
        # 10 kWh, 10 kW, rendement 1 -> 1h
        t = calcul_temps_charge(10, 10, 1.0)
        self.assertAlmostEqual(t, 1.0)
        print("Batterie: OK")

    def test_boite(self):
        # 100 Nm, 0.1m diametre -> 2000 N
        ft = calcul_force_tangentielle(100, 0.1)
        self.assertEqual(ft, 2000)
        print("Boite Crabots: OK")

    def test_moteur_elec(self):
        # 1000 N, 10 m/s -> 10000 W
        p = calcul_puissance_roue(1000, 10)
        self.assertEqual(p, 10000)
        print("Moteur Electrique: OK")

    def test_moteur_therm(self):
        # B=0.1, S=0.1 -> pi/4 * 0.01 * 0.1 = 0.000785...
        v = calcul_cylindree_unitaire(0.1, 0.1)
        self.assertAlmostEqual(v, 0.000785, places=5)
        print("Moteur Thermique: OK")

if __name__ == '__main__':
    unittest.main()
