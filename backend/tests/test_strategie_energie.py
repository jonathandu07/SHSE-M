# backend/tests/test_strategie_energie.py
import unittest
import math
from backend.ensemble.strategie_energie import calculer_strategie_couplage

# ==========================================================
# FIXTURES DE TEST (Valeurs arbitraires non contractuelles)
# ==========================================================

class MockComponent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockAlternateur:
    """Mock mimant l'API réelle de Alternateur.py"""
    def analyser_point_de_fonctionnement(self, **kwargs):
        rpm = kwargs.get("vitesse_rotation_rpm", 0)
        tension = kwargs.get("tension_v", 400.0)
        # Simulation d'un rendement constant de 0.9 pour le test
        # (Aucun KV ici, juste une réponse structurée métier)
        p_meca = (rpm * 100 * 2 * math.pi) / 60 # On simule un couple de 100Nm constant pour le mock
        return {
            "sortie_electrique": {"puissance_utile_w": p_meca * 0.9},
            "rendement": {"eta_sur_pertes_connues": 0.9},
            "pertes": {"pertes_connues_total_w": p_meca * 0.1},
            "inconnues": {"impossibles": [], "partielles": []}
        }

# ==========================================================
# TESTS UNITAIRES
# ==========================================================

class TestStrategieEnergie(unittest.TestCase):
    def setUp(self):
        # Fixtures arbitraires pour initialiser les tests
        self.composants = {
            "batterie": MockComponent(
                capacite_ah=100.0,
                c_rate_charge_max=2.0,
                temp_cellule_critique_c=60.0
            ),
            "alternateur": MockAlternateur(),
            "boite_crabots": MockComponent(rapports={"direct": 1.0}),
            "moteur_thermique": MockComponent(rpm_min=800, rpm_max=6000),
            "deplaceur": MockComponent(resistance_thermique_k_w=0.1, capacite_thermique_j_k=100.0)
        }
        
        self.etat = {
            "puissance_traction_roue_w": 20000.0,
            "batterie_soc": 0.5,
            "batterie_soh": 0.9,
            "batterie_temp_c": 25.0,
            "v_bus_dc_v": 400.0,
            "temps_disponible_s": 1.0,
            "bornes_recherche": {
                "rpm_min": 1000, "rpm_max": 3000, "rpm_step": 500,
                "couple_min": 50, "couple_max": 150, "couple_step": 50
            }
        }

    def test_securite_temperature_coupe_charge(self):
        """Vérifie que la surchauffe batterie coupe la charge mais définit le mode dégradé."""
        self.etat["batterie_temp_c"] = 65.0 # > 60.0
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["mode_energetique"], "mode_degrade")
        self.assertEqual(res["bilan_bus_dc"]["p_charge_cible_w"], 0.0)

    def test_inconnue_soh_propagée(self):
        """Vérifie que l'absence de SoH remonte en inconnue partielle."""
        self.etat["batterie_soh"] = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any(i["nom"] == "p_charge_max_soh_w" for i in res["inconnues"]["partielles"]))

    def test_transitoire_impossible_parametres_manquants(self):
        """Vérifie que l'absence de Cth empêche la validation transitoire mais ne plante pas."""
        self.composants["deplaceur"].capacite_thermique_j_k = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["validation_transitoire"]["statut"], "impossible")
        self.assertIn("Manque Rth ou Cth", res["validation_transitoire"]["raison"])

    def test_aucun_point_atteignable(self):
        """Vérifie le rapport d'impossibilité si la puissance cible est hors grille."""
        self.etat["puissance_traction_roue_w"] = 1000000.0 # Demande impossible (1MW)
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertIsNone(res["decision"])
        self.assertTrue(any(i["nom"] == "point_optimal" for i in res["inconnues"]["impossibles"]))

if __name__ == "__main__":
    unittest.main()
