import unittest
import sys
import os

# Ajout du path pour les imports locaux
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.consistency.dimensionnement import calcul_puissance_vilebrequin, calcul_cylindree_totale
from backend.consistency.optimizer import ArchitectureOptimizer

class TestConsistency(unittest.TestCase):
    def test_power_conversion(self):
        # 150kW roues -> ~207.4kW vilo (avec 92% moteur elec)
        p_vilo = calcul_puissance_vilebrequin(150000, 20000, 5000)
        self.assertAlmostEqual(p_vilo / 1000, 207.4, places=1)

    def test_displacement_formula(self):
        # 193kW, 3000rpm, 15bar -> 5146.7cc
        p_vilo = 193000
        pme = 15e5
        rpm = 3000
        vd = calcul_cylindree_totale(p_vilo, pme, rpm)
        self.assertAlmostEqual(vd * 1e6, 5146.7, places=1)

    def test_bore_max_enforcement(self):
        optimizer = ArchitectureOptimizer(bore_max_mm=133.3)
        # On force une cylindrée unitaire qui exigerait un bore de 140mm
        # N=1? Non, on check N dans le loop.
        # Si N=2, Vd=5.1L -> Vu=2.55L. B = cuberoot(4*2.55/pi) = 148mm
        res = optimizer._evaluate_n(2, 0.005146, 3000, 15e5, 2.0, 2.0)
        
        # Le bore doit être capé à 133.3
        self.assertLessEqual(res["bore_mm"], 133.3001)
        # La configuration doit être invalide à cause du ratio S/B ou de la vitesse piston car stroke a augmenté
        self.assertFalse(res["valide"])

    def test_maintenance_cost_scaling(self):
        optimizer = ArchitectureOptimizer()
        vd = 0.005
        rpm = 3000
        pme = 15e5
        
        c2 = optimizer._evaluate_n(2, vd, rpm, pme, 2.0, 2.0)["cout_maint"]
        c12 = optimizer._evaluate_n(12, vd, rpm, pme, 2.0, 2.0)["cout_maint"]
        
        # Le coût pour 12 cylindres doit être significativement plus élevé que pour 2
        self.assertGreater(c12, c2)

if __name__ == '__main__':
    unittest.main()
