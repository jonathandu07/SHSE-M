# backend/tests/test_strategie_energie.py
import unittest
import math
from backend.ensemble.strategie_energie import calculer_strategie_couplage

# FIXTURES DE TEST
FIXTURE_REND_ALT = 0.9
FIXTURE_VBUS = 400.0

class MockComponent:
    def __init__(self, **kwargs):
        for k, v in kwargs.items(): setattr(self, k, v)

class MockAlternateur:
    def analyser_point_de_fonctionnement(self, **kwargs):
        rpm, v, c = kwargs.get("vitesse_rotation_rpm"), kwargs.get("tension_v"), kwargs.get("couple_nm")
        if c is None: raise TypeError("API sans couple") # Simule API ancienne
        p_meca = (rpm * c * 2 * math.pi) / 60
        return {"sortie_electrique": {"puissance_utile_w": p_meca * FIXTURE_REND_ALT}, "rendement": {"eta_sur_pertes_connues": FIXTURE_REND_ALT}, "pertes": {"pertes_connues_total_w": p_meca * (1.0 - FIXTURE_REND_ALT)}, "inconnues": {"impossibles": [], "partielles": []}}

class TestStrategieEnergieV6(unittest.TestCase):
    def setUp(self):
        self.composants = {
            "batterie": MockComponent(capacite_ah=100.0, c_rate_charge_max=2.0, temp_cellule_critique_c=60.0, temp_derating_seuil_c=50.0, soh_seuil_protection=0.85, courant_max_bus_a=200.0, soc_seuil_soutien_traction=0.15, soc_seuil_fin_recharge=0.8, loi_reduction_puissance_soh=lambda p, s: p * s),
            "alternateur": MockAlternateur(), "boite_crabots": MockComponent(rapports={"direct": 1.0}), "moteur_thermique": MockComponent(rpm_min=800, rpm_max=6000), "moteur_electrique": MockComponent(rendement_moteur_electrique=0.95), "deplaceur": MockComponent(resistance_thermique_k_w=0.1, capacite_thermique_j_k=100.0)
        }
        self.etat = {
            "puissance_traction_roue_w": 20000.0, "batterie_soc": 0.5, "batterie_soh": 0.9, "batterie_temp_c": 25.0, "v_bus_dc_v": FIXTURE_VBUS, "temps_disponible_s": 1.0, "point_actuel_thermique": {"rpm": 800, "couple_nm": 0.0}, "tol_puissance_relative": 0.05,
            "bornes_recherche": {"rpm_min": 1000, "rpm_max": 3000, "rpm_step": 500, "couple_min": 50, "couple_max": 600, "couple_step": 50}
        }

    def test_absence_loi_soh_bloque_recommandation(self):
        """Si la loi SoH est absente, la puissance recommandee devient inconnue."""
        self.composants["batterie"].loi_reduction_puissance_soh = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertIsNone(res["enveloppe_batterie"].p_charge_recommandee_w)
        self.assertTrue(any("loi_reduction_puissance_soh" in i["raison"] for i in res["inconnues"]["partielles"]))

    def test_manque_tolerance_bloque_filtrage(self):
        """Sans tol_puissance_relative, le filtrage est impossible."""
        self.etat["tol_puissance_relative"] = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any("filtrage" in i["nom"] for i in res["inconnues"]["impossibles"]))

    def test_diagnostic_transitoire_complet(self):
        """Vérifie que les données manquantes du transitoire sont listées précisément."""
        self.composants["deplaceur"].resistance_thermique_k_w = None
        self.composants["deplaceur"].capacite_thermique_j_k = None
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertIn("Rth, Cth", res["validation_transitoire"]["raison"])

    def test_api_alternateur_sans_couple_echec(self):
        """Si l'alternateur ne prend pas le couple, les points sont impossibles."""
        # On ne change rien au mock, il lève TypeError si couple est passé (on le simule ainsi)
        # Mais ici le code de strategie_energie attrape TypeError et marque impossible.
        res = calculer_strategie_couplage(self.etat, self.composants)
        # On retire la tolérance pour être sûr que l'échec vient de l'API
        self.etat["puissance_traction_roue_w"] = 0.0 # On ne veut que de la charge
        # On force un alternateur qui crache une erreur (on redéfinit la méthode pour simuler l'échec)
        def fn_fail(**kwargs): raise TypeError("API obsolete")
        self.composants["alternateur"].analyser_point_de_fonctionnement = fn_fail
        res = calculer_strategie_couplage(self.etat, self.composants)
        self.assertTrue(any("Aucun point atteignable" in i["raison"] for i in res["inconnues"]["impossibles"]))

if __name__ == "__main__":
    unittest.main()
