# backend/tests/test_strategie_energie.py
import unittest
from backend.ensemble.strategie_energie import calculer_strategie_couplage

class MockComponent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class TestStrategieEnergie(unittest.TestCase):
    def setUp(self):
        self.composants = {
            "batterie": MockComponent(
                capacite_ah=100.0,
                c_rate_charge_max=2.0,
                temp_cellule_critique_c=60.0,
                soh=0.9
            ),
            "alternateur": MockComponent(
                resistance_phase_ohm=0.001,
                constante_tension_kv=10.0,
                rpm_max=8000,
                couple_max=400
            ),
            "boite_crabots": MockComponent(
                rapports={"direct": 1.0, "court": 2.0}
            ),
            "moteur_thermique": MockComponent(
                rpm_min=800,
                rpm_max=6000
            ),
            "deplaceur": MockComponent(
                resistance_thermique_k_w=0.1,
                capacite_thermique_j_k=100.0
            )
        }
        
        self.etat = {
            "puissance_traction_roue_w": 20000.0,
            "batterie_soc": 0.5,
            "batterie_soh": 0.9,
            "batterie_temp_c": 25.0,
            "v_bus_dc_v": 400.0,
            "bornes_recherche": {
                "rpm_min": 1000, "rpm_max": 5000, "rpm_step": 500,
                "couple_min": 10, "couple_max": 400, "couple_step": 20
            }
        }

    def test_securite_temperature(self):
        """Vérifie que la surchauffe batterie coupe la charge."""
        self.etat["batterie_temp_c"] = 65.0 # > 60.0
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["mode_energetique"], "mode_degrade")
        self.assertEqual(res["bilan_bus_dc"]["p_charge_cible_w"], 0.0)

    def test_inconnue_soh(self):
        """Vérifie que l'absence de SoH est rapportée mais n'arrête pas tout."""
        self.etat["batterie_soh"] = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any(i["nom"] == "p_charge_max_soh_w" for i in res["inconnues"]["partielles"]))
        self.assertIsNotNone(res["decision"]) # On a quand même une décision basée sur le C-rate

    def test_inertie_thermique(self):
        """Vérifie que l'inertie limite la validation transitoire."""
        # On augmente l'inertie (Cth énorme)
        self.composants["deplaceur"].capacite_thermique_j_k = 100000.0
        self.etat["temps_disponible_s"] = 0.5 # Temps très court
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["validation_transitoire"]["statut"], "limite_par_inertie")

if __name__ == "__main__":
    unittest.main()
