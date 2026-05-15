# backend/tests/test_strategie_energie.py
import unittest
import math
from backend.ensemble.strategie_energie import calculer_strategie_couplage

# ==========================================================
# FIXTURES DE TEST (Valeurs arbitraires pour validation logique)
# Ne représentent PAS des valeurs de conception réelles.
# ==========================================================
FIXTURE_TEST_REND_ALT = 0.9      # Arbitraire : rendement alternateur stable
FIXTURE_TEST_VBUS = 400.0        # Arbitraire : tension bus nominale
FIXTURE_TEST_CAP_AH = 100.0      # Arbitraire : capacité batterie
FIXTURE_TEST_SOC_MIN = 0.15      # Arbitraire : seuil soutien traction
FIXTURE_TEST_SOC_MAX = 0.8       # Arbitraire : seuil fin recharge
FIXTURE_TEST_TOL_P = 0.05        # Arbitraire : tolérance de puissance relative
FIXTURE_TEST_TOL_TRANS = 0.1     # Arbitraire : tolérance transitoire relative

def FIXTURE_LOI_SOH_ARBITRAIRE(p_crate, soh):
    """Loi arbitraire pour le test. Ne pas utiliser en production."""
    return p_crate * soh

class MockComponent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items(): setattr(self, k, v)

class MockAlternateur:
    """Mock mimant l'API réelle avec gestion du couple."""
    def analyser_point_de_fonctionnement(self, **kwargs):
        rpm, v, c = kwargs.get("vitesse_rotation_rpm"), kwargs.get("tension_v"), kwargs.get("couple_nm")
        if c is None: raise TypeError("API sans couple")
        p_meca = (rpm * c * 2 * math.pi) / 60
        return {
            "sortie_electrique": {"puissance_utile_w": p_meca * FIXTURE_TEST_REND_ALT},
            "rendement": {"eta_sur_pertes_connues": FIXTURE_TEST_REND_ALT},
            "pertes": {"pertes_connues_total_w": p_meca * (1.0 - FIXTURE_TEST_REND_ALT)},
            "inconnues": {"impossibles": [], "partielles": []}
        }

class TestStrategieEnergieV7(unittest.TestCase):
    def setUp(self):
        self.composants = {
            "batterie": MockComponent(
                capacite_ah=FIXTURE_TEST_CAP_AH, c_rate_charge_max=2.0, temp_cellule_critique_c=60.0, 
                temp_derating_seuil_c=50.0, soh_seuil_protection=0.85, courant_max_bus_a=200.0,
                soc_seuil_soutien_traction=FIXTURE_TEST_SOC_MIN, soc_seuil_fin_recharge=FIXTURE_TEST_SOC_MAX,
                loi_reduction_puissance_soh=FIXTURE_LOI_SOH_ARBITRAIRE
            ),
            "alternateur": MockAlternateur(), "boite_crabots": MockComponent(rapports={"direct": 1.0}),
            "moteur_thermique": MockComponent(rpm_min=800, rpm_max=6000),
            "moteur_electrique": MockComponent(rendement_moteur_electrique=0.95),
            "deplaceur": MockComponent(resistance_thermique_k_w=0.1, capacite_thermique_j_k=100.0)
        }
        self.etat = {
            "puissance_traction_roue_w": 20000.0, "batterie_soc": 0.5, "batterie_soh": 0.9, "batterie_temp_c": 25.0,
            "v_bus_dc_v": FIXTURE_TEST_VBUS, "temps_disponible_s": 1.0, "point_actuel_thermique": {"rpm": 800, "couple_nm": 0.0},
            "tol_puissance_relative": FIXTURE_TEST_TOL_P, "tol_transitoire_relative": FIXTURE_TEST_TOL_TRANS,
            "bornes_recherche": {
                "rpm_min": 1000, "rpm_max": 3000, "rpm_step": 500,
                "couple_min": 50, "couple_max": 600, "couple_step": 50
            }
        }

    def test_rigueur_plage_thermique_incoherente(self):
        """Vérifie qu'une plage de derating nulle lève une inconnue explicite."""
        self.composants["batterie"].temp_derating_seuil_c = 60.0 # Egale à temp_critique
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any("incohérent" in i["raison"] for i in res["inconnues"]["partielles"]))

    def test_propagation_inconnues_globales_carto(self):
        """Vérifie que les erreurs de bornes (ex: rpm_step=0) remontent au rapport final."""
        self.etat["bornes_recherche"]["rpm_step"] = 0
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any("strictement positif" in i["raison"] for i in res["inconnues"]["impossibles"]))

    def test_decideur_p_charge_decide_vs_inconnu(self):
        """Prouve la différence entre p_charge=0.0 (EV Only) et p_charge=None (Inconnu)."""
        # Cas EV Only : SoC élevé, p_charge doit être 0.0
        self.etat["batterie_soc"] = 0.9
        res_ev = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res_ev["bilan_bus_dc"]["p_charge_cible_w"], 0.0)
        
        # Cas Recharge : SoC faible mais enveloppe incomplète (manque loi SoH)
        self.etat["batterie_soc"] = 0.5
        self.composants["batterie"].loi_reduction_puissance_soh = None
        res_recharge = calculer_strategie_couplage(self.etat, self.composants)
        self.assertIsNone(res_recharge["bilan_bus_dc"]["p_charge_cible_w"])

    def test_score_priorise_donnee_connue(self):
        """Vérifie que le tri préfère un rendement connu à un inconnu (drapeau 0 vs 1)."""
        # Ici tous les points mockés ont un rendement. Le score[7] (rend_inc) doit être 0.
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertEqual(res["point_retenu"]["alternateur"]["score_lexico"][7], 0)

if __name__ == "__main__":
    unittest.main()
