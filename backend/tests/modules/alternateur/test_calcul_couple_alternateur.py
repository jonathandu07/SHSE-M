# backend/tests/modules/alternateur/test_calcul_couple_alternateur.py

from __future__ import annotations

import logging
import math
import platform
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from backend.components.alternateur.modules.calcul_couple_alternateur import calcul_couple_alternateur


# =============================================================================
# LOGS (backend/logs/<nom_test>_YYYYMMDD_HHMMSS.log)
# =============================================================================

_LOGGER: Optional[logging.Logger] = None
_LOG_PATH: Optional[Path] = None


def _trouver_backend_dir() -> Path:
    """
    Trouve le dossier 'backend' à partir de l'emplacement du fichier de test.
    Robuste même si l'arborescence change légèrement.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "backend":
            return parent
    # Fallback probable: .../backend/tests/modules/alternateur/test_x.py => parents[3] == backend
    return here.parents[3]


def _creer_logger_fichier() -> Tuple[logging.Logger, Path]:
    backend_dir = _trouver_backend_dir()
    logs_dir = backend_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Nom: <nom_du_fichier_test>_YYYYMMDD_HHMMSS.log
    base = Path(__file__).stem  # ex: test_calcul_couple_alternateur
    # On prend l'heure locale du système (ton environnement). Format sûr pour Windows.
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"{base}_{ts}.log"

    logger = logging.getLogger(f"backend.tests.{base}")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # éviter doublons si config globale

    # Évite de ré-attacher des handlers si le module est rechargé
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_path) for h in logger.handlers):
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger, log_path


def setUpModule() -> None:
    """
    Appelé par unittest avant l'exécution des tests de CE module.
    """
    global _LOGGER, _LOG_PATH
    _LOGGER, _LOG_PATH = _creer_logger_fichier()
    _LOGGER.info("=== DÉBUT TESTS ===")
    _LOGGER.info("Module de test : %s", __file__)
    _LOGGER.info("Log file       : %s", str(_LOG_PATH))
    _LOGGER.info("Python         : %s", sys.version.replace("\n", " "))
    _LOGGER.info("Platform       : %s | %s", platform.platform(), platform.machine())


def tearDownModule() -> None:
    """
    Appelé par unittest après l'exécution des tests de CE module.
    """
    global _LOGGER
    if _LOGGER is not None:
        _LOGGER.info("=== FIN TESTS ===")


def _log_info(msg: str, *args) -> None:
    if _LOGGER is not None:
        _LOGGER.info(msg, *args)


class TestCalculCoupleAlternateur(unittest.TestCase):
    def setUp(self) -> None:
        self._t0 = time.perf_counter()
        _log_info("--- START %s", self.id())

    def tearDown(self) -> None:
        dt_s = time.perf_counter() - getattr(self, "_t0", time.perf_counter())

        # Déterminer le statut du test (OK / FAIL / ERROR) de façon fiable
        status = "OK"
        details = ""

        outcome = getattr(self, "_outcome", None)
        result = getattr(outcome, "result", None) if outcome is not None else None

        if result is not None:
            tid = self.id()
            for t, tb in getattr(result, "failures", []):
                if getattr(t, "id", lambda: "")() == tid:
                    status = "FAIL"
                    details = tb
                    break
            if status == "OK":
                for t, tb in getattr(result, "errors", []):
                    if getattr(t, "id", lambda: "")() == tid:
                        status = "ERROR"
                        details = tb
                        break

        _log_info("--- END   %s | %s | %.6f s", self.id(), status, dt_s)
        if details:
            # Traceback déjà formaté par unittest
            _log_info("TRACEBACK:\n%s", details)

    def assertIsClose(self, a: float, b: float, *, rel: float = 1e-12, abs_: float = 0.0) -> None:
        ok = math.isclose(a, b, rel_tol=rel, abs_tol=abs_)
        if not ok:
            _log_info("ASSERT isclose FAILED | a=%r b=%r rel=%r abs=%r", a, b, rel, abs_)
        self.assertTrue(ok, msg=f"Attendu ~{b!r} mais reçu {a!r}")

    # --------------------------
    # Cas nominaux
    # --------------------------

    def test_nominal_sans_pertes(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = 100.0
        attendu = (P_e / eta) / omega

        couple = calcul_couple_alternateur(P_e, eta, omega)

        _log_info("calc | P_e=%g W | eta=%g | omega=%g rad/s | pertes=0 | couple=%g N.m | attendu=%g",
                  P_e, eta, omega, couple, attendu)

        self.assertIsInstance(couple, float)
        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_nominal_avec_pertes_fixes(self) -> None:
        P_e = 1000.0
        pertes = 100.0
        eta = 0.9
        omega = 100.0
        attendu = ((P_e + pertes) / eta) / omega

        couple = calcul_couple_alternateur(P_e, eta, omega, pertes_fixes_w=pertes)

        _log_info("calc | P_e=%g W | eta=%g | omega=%g rad/s | pertes=%g W | couple=%g N.m | attendu=%g",
                  P_e, eta, omega, pertes, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_rendement_un(self) -> None:
        P_e = 250.0
        eta = 1.0
        omega = 50.0
        attendu = (P_e / eta) / omega  # 5.0

        couple = calcul_couple_alternateur(P_e, eta, omega)

        _log_info("calc | P_e=%g W | eta=%g | omega=%g rad/s | couple=%g N.m | attendu=%g",
                  P_e, eta, omega, couple, attendu)

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

        _log_info("calc | mode=conserver | P_e=%g | eta=%g | omega=%g | couple=%g | attendu=%g",
                  P_e, eta, omega, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_omega_negatif_mode_abs_omega(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = -100.0
        attendu = (P_e / eta) / abs(omega)  # positif

        couple = calcul_couple_alternateur(P_e, eta, omega, mode_signe="abs_omega")

        _log_info("calc | mode=abs_omega | P_e=%g | eta=%g | omega=%g | couple=%g | attendu=%g",
                  P_e, eta, omega, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_regeneration_puissance_negative(self) -> None:
        P_e = -500.0
        eta = 0.8
        omega = 100.0
        attendu = (P_e / eta) / omega  # -6.25

        couple = calcul_couple_alternateur(P_e, eta, omega)

        _log_info("calc | regen | P_e=%g | eta=%g | omega=%g | couple=%g | attendu=%g",
                  P_e, eta, omega, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_regeneration_omega_negatif_mode_conserver(self) -> None:
        P_e = -500.0
        eta = 0.8
        omega = -100.0
        attendu = (P_e / eta) / omega  # positif

        couple = calcul_couple_alternateur(P_e, eta, omega, mode_signe="conserver")

        _log_info("calc | regen+omega- | mode=conserver | P_e=%g | eta=%g | omega=%g | couple=%g | attendu=%g",
                  P_e, eta, omega, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_clamp_non_negative_force_zero_si_couple_negatif(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = -100.0  # couple négatif si mode_signe="conserver"

        couple = calcul_couple_alternateur(
            P_e, eta, omega, clamp_non_negative=True, mode_signe="conserver"
        )

        _log_info("calc | clamp=True | mode=conserver | P_e=%g | eta=%g | omega=%g | couple=%g (attendu 0)",
                  P_e, eta, omega, couple)

        self.assertIsClose(couple, 0.0, rel=0.0, abs_=0.0)

    def test_clamp_non_negative_ne_change_pas_si_deja_positif(self) -> None:
        P_e = 1000.0
        eta = 0.9
        omega = 100.0
        attendu = (P_e / eta) / omega

        couple = calcul_couple_alternateur(P_e, eta, omega, clamp_non_negative=True)

        _log_info("calc | clamp=True | P_e=%g | eta=%g | omega=%g | couple=%g | attendu=%g",
                  P_e, eta, omega, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    # --------------------------
    # epsilon_omega / division par ~0
    # --------------------------

    def test_omega_zero_refuse(self) -> None:
        _log_info("expect ValueError | omega=0")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 0.0)

    def test_omega_trop_proche_zero_refuse_selon_epsilon(self) -> None:
        _log_info("expect ValueError | omega=1e-13 | epsilon=1e-12")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 1e-13, epsilon_omega=1e-12)

    def test_omega_passe_si_epsilon_plus_petit(self) -> None:
        omega = 1e-13
        eps = 1e-14
        couple = calcul_couple_alternateur(100.0, 0.9, omega, epsilon_omega=eps)
        _log_info("calc | omega=%g | epsilon=%g | couple=%g | finite=%s",
                  omega, eps, couple, str(math.isfinite(couple)))
        self.assertTrue(math.isfinite(couple))

    def test_epsilon_invalide_refuse(self) -> None:
        _log_info("expect ValueError | epsilon=0")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, epsilon_omega=0.0)

        _log_info("expect ValueError | epsilon=-1")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, epsilon_omega=-1.0)

        _log_info("expect ValueError | epsilon=NaN")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, epsilon_omega=float("nan"))

    # --------------------------
    # Validations de domaine (rendement)
    # --------------------------

    def test_rendement_zero_refuse(self) -> None:
        _log_info("expect ValueError | eta=0")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.0, 10.0)

    def test_rendement_negatif_refuse(self) -> None:
        _log_info("expect ValueError | eta=-0.5")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, -0.5, 10.0)

    def test_rendement_superieur_un_refuse(self) -> None:
        _log_info("expect ValueError | eta=1.0000001")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 1.0000001, 10.0)

    # --------------------------
    # mode_signe
    # --------------------------

    def test_mode_signe_invalide_refuse(self) -> None:
        _log_info("expect ValueError | mode_signe=xyz")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, mode_signe="xyz")  # type: ignore[arg-type]

    # --------------------------
    # Non-finis (NaN/inf)
    # --------------------------

    def test_puissance_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | P_e=NaN/inf")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(float("nan"), 0.9, 10.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(float("inf"), 0.9, 10.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(float("-inf"), 0.9, 10.0)

    def test_rendement_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | eta=NaN/inf")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, float("nan"), 10.0)
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, float("inf"), 10.0)

    def test_omega_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | omega=NaN/inf")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, float("nan"))
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, float("inf"))

    def test_pertes_non_finies_refuse(self) -> None:
        _log_info("expect ValueError | pertes=NaN/inf")
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, pertes_fixes_w=float("nan"))
        with self.assertRaises(ValueError):
            calcul_couple_alternateur(100.0, 0.9, 10.0, pertes_fixes_w=float("inf"))

    # --------------------------
    # Cas limites utiles
    # --------------------------

    def test_pertes_negatives_autorisees_mathematiquement(self) -> None:
        P_e = 1000.0
        pertes = -100.0
        eta = 0.9
        omega = 100.0
        attendu = ((P_e + pertes) / eta) / omega

        couple = calcul_couple_alternateur(P_e, eta, omega, pertes_fixes_w=pertes)

        _log_info("calc | pertes négatives | P_e=%g | pertes=%g | eta=%g | omega=%g | couple=%g | attendu=%g",
                  P_e, pertes, eta, omega, couple, attendu)

        self.assertIsClose(couple, attendu, rel=1e-12)

    def test_entiers_acceptes(self) -> None:
        couple = calcul_couple_alternateur(1000, 1, 100)  # type: ignore[arg-type]
        _log_info("calc | ints | P_e=1000 | eta=1 | omega=100 | couple=%g | attendu=10", couple)
        self.assertIsClose(couple, 10.0, rel=0.0, abs_=0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
