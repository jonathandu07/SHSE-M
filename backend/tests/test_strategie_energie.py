# backend/tests/test_strategie_energie.py
import unittest
import math
from backend.ensemble.strategie_energie import calculer_strategie_couplage

# ==========================================================
# FIXTURES DE TEST (Valeurs arbitraires pour validation logique)
# ==========================================================
FIXTURE_TEST_RENDEMENT_ALTERNATEUR = 0.9 # Valeur arbitraire de test
FIXTURE_TEST_VBUS = 400.0
FIXTURE_TEST_CAP_AH = 100.0

class MockComponent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockAlternateur:
    """Mock mimant l'API réelle pour tester la logique de tri."""
    def analyser_point_de_fonctionnement(self, **kwargs):
        rpm = kwargs.get("vitesse_rotation_rpm")
        v_bus = kwargs.get("tension_v")
        couple = kwargs.get("couple_nm") # Récupération réelle du couple
        
        if any(x is None for x in (rpm, v_bus, couple)):
            return {"inconnues": {"impossibles": [{"nom": "point", "raison": "Manque rpm, v_bus ou couple"}]}}
            
        p_meca = (rpm * couple * 2 * math.pi) / 60
        return {
            "sortie_electrique": {"puissance_utile_w": p_meca * FIXTURE_TEST_RENDEMENT_ALTERNATEUR},
            "rendement": {"eta_sur_pertes_connues": FIXTURE_TEST_RENDEMENT_ALTERNATEUR},
            "pertes": {"pertes_connues_total_w": p_meca * (1.0 - FIXTURE_TEST_RENDEMENT_ALTERNATEUR)},
            "inconnues": {"impossibles": [], "partielles": []}
        }

# ==========================================================
# TESTS UNITAIRES
# ==========================================================

class TestStrategieEnergie(unittest.TestCase):
    def setUp(self):
        # Configuration batterie sans aucune invention
        self.composants = {
            "batterie": MockComponent(
                capacite_ah=FIXTURE_TEST_CAP_AH,
                c_rate_charge_max=2.0,
                temp_cellule_critique_c=60.0,
                temp_derating_seuil_c=50.0,
                soh_seuil_protection=0.85,
                courant_max_bus_a=200.0,
                soc_seuil_soutien_traction=0.15,
                soc_seuil_fin_recharge=0.8
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

    def test_rigueur_seuil_soc_inconnu(self):
        """Vérifie que sans seuil SoC, le système ne décide pas du mode soutien/recharge."""
        self.composants["batterie"].soc_seuil_soutien_traction = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["mode_energetique"], "ev_only")
        self.assertTrue(any("arbitrage_mode" in i["nom"] for i in res["inconnues"]["partielles"]))

    def test_lexicographie_priorite_donnee_connue(self):
        """Vérifie que le tri privilégie un point avec rendement connu sur un point inconnu."""
        res = calculer_strategie_couplage(self.etat, self.composants)
        # On vérifie que le score_lexico[7] (rendement_inconnu) est à 0 pour le point retenu
        self.assertEqual(res["point_retenu"]["alternateur"].score_lexico[7], 0)

    def test_traction_bus_dc_depend_rendement_me(self):
        """Vérifie que la puissance bus DC n'est pas calculée si le rendement moteur elec manque."""
        self.composants["moteur_electrique"].rendement_moteur_electrique = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertIsNone(res["bilan_bus_dc"]["p_gen_requise_w"])
        self.assertTrue(any("rendement_moteur_electrique" in i["nom"] for i in res["inconnues"]["partielles"]))

    def test_transitoire_impossible_si_point_actuel_manquant(self):
        """Vérifie que le transitoire est déclaré impossible sans point actuel thermique."""
        self.etat["point_actuel_thermique"] = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["validation_transitoire"]["statut"], "impossible")

if __name__ == "__main__":
    unittest.main()
