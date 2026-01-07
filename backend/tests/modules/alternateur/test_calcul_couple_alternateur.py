# backend/tests/modules/alternateur/test_calcul_couple_alternateur.py

from __future__ import annotations

import math
import unittest

from backend.modules.alternateur.calcul_couple_alternateur import calcul_couple_alternateur


class TestCalculCoupleAlternateur(unittest.TestCase):
    def assertIsClose(self, a: float, b: float, *, rel: float = 1e-12, abs_: float = 0.0) -> None:
        self.assertTrue(
            math.isclose(a, b, rel_tol=rel, abs_tol=abs_),
            msg=f"Attendu ~{b!r} mais reçu {a!r}",
        )

    # --------------------------
    # Cas nominaux
    # --------------------------

    def test_nominal_sans_pertes(self) -> None:
        # P_mec = P_e / eta ; T = P_mec / omega
        P_e = 1000.0
        eta = 0.9
        omega = 100.0
        attendu = (P_e / eta) / omega
        couple = calcul_couple_alternateur(P_e, eta, omega)
        self.assertIsInstance(couple, float)
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_nominal_avec_pertes_fixes(self) -> None:
        P_e = 1000.0
        pertes = 100.0
        eta = 0.9
        omega = 100.0
        attendu = ((P_e + pertes) / eta) / omega
        couple = calcul_couple_alternateur(P_e, eta, omega, pertes_fixes_w=pertes)
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_rendement_un(self) -> None:
        P_e = 250.0
        eta = 1.0
        omega = 50.0
        attendu = (P_e / eta) / omega  # 5.0
        couple = calcul_couple_alternateur(P_e, eta, omega)
        self.assertIsClose(couple, attendu, rel=0.0, abs_=0.0)

    # --------------------------
    # Signe / conventions
    # --------------------------

    def test_omega_negatif_mode_conserver(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = -100.0
        attendu = (P_e / eta) / omega  # négatif
        couple = calcul_couple_alternateur(P_e, eta, omega, mode_signe="conserver")
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_omega_negatif_mode_abs_omega(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = -100.0
        attendu = (P_e / eta) / abs(omega)  # positif
        couple = calcul_couple_alternateur(P_e, eta, omega, mode_signe="abs_omega")
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_regeneration_puissance_negative(self) -> None:
        P_e = -500.0
        eta = 0.8
        omega = 100.0
        attendu = (P_e / eta) / omega  # -6.25
        couple = calcul_couple_alternateur(P_e, eta, omega)
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_regeneration_omega_negatif_mode_conserver(self) -> None:
        # P_mec négatif et omega négatif => couple positif
        P_e = -500.0
        eta = 0.8
        omega = -100.0
        attendu = (P_e / eta) / omega
        couple = calcul_couple_alternateur(P_e, eta, omega, mode_signe="conserver")
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_clamp_non_negative_force_zero_si_couple_negatif(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = -100.0  # couple négatif si mode_signe="conserver"
        couple = calcul_couple_alternateur(
            P_e, eta, omega, clamp_non_negative=True, mode_signe="conserver"
        )
        self.assertIsClose(couple, 0.0, rel=0.0, abs_=0.0)

    def test_clamp_non_negative_ne_change_pas_si_deja_positif(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = 100.0
        attendu = (P_e / eta) / omega
        couple = calcul_couple_alternateur(P_e, eta, omega, clamp_non_negative=True)
        self.assertIsClose(couple, attendu, rel=1e-12)

    # --------------------------
    # epsilon_omega / division par ~0
    # --------------------------

    def test_omega_zero_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 0.0)

    def test_omega_trop_proche_zero_refuse_selon_epsilon(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 1e-13, epsilon_omega=1e-12)

    def test_omega_passe_si_epsilon_plus_petit(self) -> None:
        omega = 1e-13
        couple = calcul_couple_alternateur(100.0, 0.9, omega, epsilon_omega=1e-14)
        self.assertTrue(math.isfinite(couple))

    def test_epsilon_invalide_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, epsilon_omega=0.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, epsilon_omega=-1.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, epsilon_omega=float("nan"))

    # --------------------------
    # Validations de domaine (rendement)
    # --------------------------

    def test_rendement_zero_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.0, 10.0)

    def test_rendement_negatif_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, -0.5, 10.0)

    def test_rendement_superieur_un_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 1.0000001, 10.0)

    # --------------------------
    # mode_signe
    # --------------------------

    def test_mode_signe_invalide_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, mode_signe="xyz")  # type: ignore[arg-type]

    # --------------------------
    # Non-finis (NaN/inf)
    # --------------------------

    def test_puissance_non_finie_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(float("nan"), 0.9, 10.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(float("inf"), 0.9, 10.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(float("-inf"), 0.9, 10.0)

    def test_rendement_non_fini_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, float("nan"), 10.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, float("inf"), 10.0)

    def test_omega_non_fini_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, float("nan"))
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, float("inf"))

    def test_pertes_non_finies_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, pertes_fixes_w=float("nan"))
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, pertes_fixes_w=float("inf"))

    # --------------------------
    # Cas limites utiles
    # --------------------------

    def test_pertes_negatives_autorisees_mathematiquement(self) -> None:
        # physiquement étrange, mais le module l'accepte : on vérifie juste le calcul
        P_e = 1000.0
        pertes = -100.0
        eta = 0.9
        omega = 100.0
        attendu = ((P_e + pertes) / eta) / omega
        couple = calcul_couple_alternateur(P_e, eta, omega, pertes_fixes_w=pertes)
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_entiers_acceptes(self) -> None:
        couple = calcul_couple_alternateur(1000, 1, 100)  # type: ignore[arg-type]
        self.assertIsClose(couple, 10.0, rel=0.0, abs_=0.0)


if __name__ == "__main__":
    unittest.main()
