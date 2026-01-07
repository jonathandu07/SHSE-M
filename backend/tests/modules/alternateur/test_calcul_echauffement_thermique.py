# backend/tests/modules/alternateur/test_calcul_echauffement_thermique.py

from __future__ import annotations

import math
import unittest

from backend.modules.alternateur.calcul_echauffement_thermique import calcul_echauffement_thermique


class TestCalculEchauffementThermique(unittest.TestCase):
    def assertIsClose(self, a: float, b: float, *, rel: float = 1e-12, abs_: float = 0.0) -> None:
        self.assertTrue(
            math.isclose(a, b, rel_tol=rel, abs_tol=abs_),
            msg=f"Attendu ~{b!r} mais reçu {a!r}",
        )

    # --------------------------
    # Cas nominaux
    # --------------------------

    def test_nominal_sans_offset(self) -> None:
        Ploss = 100.0
        Rth = 0.5
        attendu = Rth * Ploss  # 50.0
        dt = calcul_echauffement_thermique(Ploss, Rth)
        self.assertIsInstance(dt, float)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_nominal_avec_offset(self) -> None:
        Ploss = 100.0
        Rth = 0.5
        offset = 10.0
        attendu = Rth * Ploss + offset  # 60.0
        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_zero_pertes(self) -> None:
        dt = calcul_echauffement_thermique(0.0, 0.5)
        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    def test_resistance_thermique_zero(self) -> None:
        dt = calcul_echauffement_thermique(123.0, 0.0)
        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    # --------------------------
    # Signes / clamp
    # --------------------------

    def test_pertes_negatives_autorisees_sans_clamp(self) -> None:
        # modèle autorise Ploss < 0 => dt < 0 (refroidissement net / convention de signe)
        Ploss = -100.0
        Rth = 0.5
        attendu = Rth * Ploss  # -50.0
        dt = calcul_echauffement_thermique(Ploss, Rth)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_pertes_negatives_avec_clamp(self) -> None:
        Ploss = -100.0
        Rth = 0.5
        dt = calcul_echauffement_thermique(Ploss, Rth, clamp_non_negative=True)
        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    def test_offset_peut_rendre_positif_malgre_pertes_negatives(self) -> None:
        Ploss = -100.0
        Rth = 0.5  # -50
        offset = 60.0
        attendu = -50.0 + offset  # 10
        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_offset_negatif_possible(self) -> None:
        Ploss = 100.0
        Rth = 0.5  # 50
        offset = -10.0
        attendu = 40.0
        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_clamp_applique_apres_offset(self) -> None:
        # dt = Rth*Ploss + offset => négatif => clamp -> 0
        Ploss = 10.0
        Rth = 0.1  # 1
        offset = -5.0  # => -4
        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset, clamp_non_negative=True)
        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    # --------------------------
    # Rth négatif (autorisé par le module)
    # --------------------------

    def test_resistance_thermique_negative_autorisee(self) -> None:
        Ploss = 100.0
        Rth = -0.5
        attendu = -50.0
        dt = calcul_echauffement_thermique(Ploss, Rth)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_rth_negative_et_clamp(self) -> None:
        Ploss = 100.0
        Rth = -0.5  # dt = -50
        dt = calcul_echauffement_thermique(Ploss, Rth, clamp_non_negative=True)
        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    # --------------------------
    # Non-finis (NaN/inf)
    # --------------------------

    def test_puissance_non_finie_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(float("nan"), 0.5)
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(float("inf"), 0.5)
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(float("-inf"), 0.5)

    def test_rth_non_fini_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, float("nan"))
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, float("inf"))
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, float("-inf"))

    def test_offset_non_fini_refuse(self) -> None:
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, 0.5, offset_temperature=float("nan"))
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, 0.5, offset_temperature=float("inf"))
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, 0.5, offset_temperature=float("-inf"))

    # --------------------------
    # Types (int acceptés)
    # --------------------------

    def test_entiers_acceptes(self) -> None:
        dt = calcul_echauffement_thermique(100, 1, offset_temperature=0)  # type: ignore[arg-type]
        self.assertIsClose(dt, 100.0, rel=0.0, abs_=0.0)


if __name__ == "__main__":
    unittest.main()
