# backend/tests/test_strategie_energie.py
import unittest
import math
from backend.ensemble.strategie_energie import calculer_strategie_couplage

# ==========================================================
# FIXTURES DE TEST (Valeurs arbitraires pour validation logique)
# ==========================================================
FIXTURE_TEST_RENDEMENT = 0.9
FIXTURE_TEST_COUPLE_NM = 500.0
FIXTURE_TEST_VBUS = 400.0
FIXTURE_TEST_CAP_AH = 100.0

class MockComponent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockAlternateur:
    """Mock mimant l'API réelle pour tester la logique de tri."""
    def __init__(self, rendement=FIXTURE_TEST_RENDEMENT):
        self.rendement_fixe = rendement
    
    def analyser_point_de_fonctionnement(self, **kwargs):
        rpm = kwargs.get("vitesse_rotation_rpm", 0.0)
        p_meca = (rpm * FIXTURE_TEST_COUPLE_NM * 2 * math.pi) / 60
        return {
            "sortie_electrique": {"puissance_utile_w": p_meca * self.rendement_fixe},
            "rendement": {"eta_sur_pertes_connues": self.rendement_fixe},
            "pertes": {"pertes_connues_total_w": p_meca * (1.0 - self.rendement_fixe)},
            "inconnues": {"impossibles": [], "partielles": []}
        }

# ==========================================================
# TESTS UNITAIRES
# ==========================================================

class TestStrategieEnergie(unittest.TestCase):
    def setUp(self):
        # Fixtures de test
        self.composants = {
            "batterie": MockComponent(
                capacite_ah=FIXTURE_TEST_CAP_AH,
                c_rate_charge_max=2.0,
                temp_cellule_critique_c=60.0,
                temp_derating_seuil_c=50.0,
                soh_seuil_protection=0.85,
                courant_max_bus_a=200.0
            ),
            "alternateur": MockAlternateur(),
            "boite_crabots": MockComponent(rapports={"direct": 1.0}),
            "moteur_thermique": MockComponent(rpm_min=800, rpm_max=6000),
            "moteur_electrique": MockComponent(rendement_moteur_electrique=0.95),
            "deplaceur": MockComponent(resistance_thermique_k_w=0.1, capacite_thermique_j_k=100.0)
        }
        
        self.etat = {
            "puissance_traction_roue_w": 20000.0,
            "batterie_soc": 0.5,
            "batterie_soh": 0.9,
            "batterie_temp_c": 25.0,
            "v_bus_dc_v": FIXTURE_TEST_VBUS,
            "temps_disponible_s": 1.0,
            "point_actuel_thermique": {"rpm": 800, "couple_nm": 0.0},
            "bornes_recherche": {
                "rpm_min": 1000, "rpm_max": 3000, "rpm_step": 500,
                "couple_min": 50, "couple_max": 600, "couple_step": 50
            }
        }

    def test_rigueur_donnee_manquante_vbus(self):
        """Vérifie que si V_bus manque, le système s'arrête proprement sans invention."""
        self.etat["v_bus_dc_v"] = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any("V_bus" in i["raison"] for i in res["inconnues"]["impossibles"]))
        self.assertIsNone(res["decision"])

    def test_lexicographie_priorite_soh(self):
        """Vérifie que le tri lexicographique privilégie la préservation batterie."""
        # On compare deux SoH différents. Le système doit choisir celui qui maximise le SoH (score s_soh minimal)
        self.etat["batterie_soh"] = 0.95
        res1 = calculer_strategie_couplage(self.etat, self.composants)
        
        self.etat["batterie_soh"] = 0.90
        res2 = calculer_strategie_couplage(self.etat, self.composants)
        
        # Le score s_soh est (1.0 - soh). Donc 1.0 - 0.95 = 0.05 vs 1.0 - 0.90 = 0.10.
        self.assertLess(res1["point_retenu"]["score_lexico"][3], res2["point_retenu"]["score_lexico"][3])

    def test_securite_temperature_critique(self):
        """Vérifie que l'alerte thermique est levée et la charge coupée au-delà du seuil critique."""
        self.etat["batterie_temp_c"] = 65.0
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["mode_energetique"], "mode_degrade")
        self.assertIn("thermique", res["alertes"])
        self.assertEqual(res["bilan_bus_dc"]["p_charge_cible_w"], 0.0)

    def test_absence_derating_si_seuil_inconnu(self):
        """Vérifie que sans seuil de derating fourni, le derating n'est pas 'inventé'."""
        self.composants["batterie"].temp_derating_seuil_c = None
        self.etat["batterie_temp_c"] = 55.0 # Serait en derating si seuil=50
        res = calculer_strategie_couplage(self.etat, self.composants)
        # p_charge_max_temp_w doit être égal à p_charge_max_crate_w car pas de derating calculable
        env = res["enveloppe_batterie"]
        self.assertEqual(env.p_charge_max_temp_w, env.p_charge_max_crate_w)

if __name__ == "__main__":
    unittest.main()
