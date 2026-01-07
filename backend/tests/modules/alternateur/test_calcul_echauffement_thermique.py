# backend/tests/modules/alternateur/test_calcul_echauffement_thermique.py

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

from backend.modules.alternateur.calcul_echauffement_thermique import calcul_echauffement_thermique


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
    base = Path(__file__).stem  # ex: test_calcul_echauffement_thermique
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"{base}_{ts}.log"

    logger = logging.getLogger(f"backend.tests.{base}")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # éviter doublons si config globale

    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == str(log_path)
        for h in logger.handlers
    ):
        fh = logging.FileHandler(log_path, encoding="utf-8")
        fmt = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger, log_path


def setUpModule() -> None:
    global _LOGGER, _LOG_PATH
    _LOGGER, _LOG_PATH = _creer_logger_fichier()
    _LOGGER.info("=== DÉBUT TESTS ===")
    _LOGGER.info("Module de test : %s", __file__)
    _LOGGER.info("Log file       : %s", str(_LOG_PATH))
    _LOGGER.info("Python         : %s", sys.version.replace("\n", " "))
    _LOGGER.info("Platform       : %s | %s", platform.platform(), platform.machine())


def tearDownModule() -> None:
    global _LOGGER
    if _LOGGER is not None:
        _LOGGER.info("=== FIN TESTS ===")


def _log_info(msg: str, *args) -> None:
    if _LOGGER is not None:
        _LOGGER.info(msg, *args)


class TestCalculEchauffementThermique(unittest.TestCase):
    def setUp(self) -> None:
        self._t0 = time.perf_counter()
        _log_info("--- START %s", self.id())

    def tearDown(self) -> None:
        dt_s = time.perf_counter() - getattr(self, "_t0", time.perf_counter())

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
            _log_info("TRACEBACK:\n%s", details)

    def assertIsClose(self, a: float, b: float, *, rel: float = 1e-12, abs_: float = 0.0) -> None:
        ok = math.isclose(a, b, rel_tol=rel, abs_tol=abs_)
        if not ok:
            _log_info("ASSERT isclose FAILED | a=%r b=%r rel=%r abs=%r", a, b, rel, abs_)
        self.assertTrue(ok, msg=f"Attendu ~{b!r} mais reçu {a!r}")

    # --------------------------
    # Cas nominaux
    # --------------------------

    def test_nominal_sans_offset(self) -> None:
        Ploss = 100.0
        Rth = 0.5
        attendu = Rth * Ploss  # 50

        dt = calcul_echauffement_thermique(Ploss, Rth)

        _log_info("calc | Ploss=%g W | Rth=%g K/W | offset=0 | clamp=False | dt=%g | attendu=%g",
                  Ploss, Rth, dt, attendu)

        self.assertIsInstance(dt, float)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_nominal_avec_offset(self) -> None:
        Ploss = 100.0
        Rth = 0.5
        offset = 10.0
        attendu = Rth * Ploss + offset  # 60

        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset)

        _log_info("calc | Ploss=%g W | Rth=%g K/W | offset=%g | clamp=False | dt=%g | attendu=%g",
                  Ploss, Rth, offset, dt, attendu)

        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_zero_pertes(self) -> None:
        Ploss = 0.0
        Rth = 0.5
        attendu = 0.0

        dt = calcul_echauffement_thermique(Ploss, Rth)

        _log_info("calc | Ploss=%g | Rth=%g | dt=%g | attendu=%g", Ploss, Rth, dt, attendu)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_resistance_thermique_zero(self) -> None:
        Ploss = 123.0
        Rth = 0.0
        attendu = 0.0

        dt = calcul_echauffement_thermique(Ploss, Rth)

        _log_info("calc | Ploss=%g | Rth=%g | dt=%g | attendu=%g", Ploss, Rth, dt, attendu)
        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    # --------------------------
    # Signes / clamp
    # --------------------------

    def test_pertes_negatives_autorisees_sans_clamp(self) -> None:
        Ploss = -100.0
        Rth = 0.5
        attendu = Rth * Ploss  # -50

        dt = calcul_echauffement_thermique(Ploss, Rth)

        _log_info("calc | Ploss=%g | Rth=%g | clamp=False | dt=%g | attendu=%g",
                  Ploss, Rth, dt, attendu)

        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_pertes_negatives_avec_clamp(self) -> None:
        Ploss = -100.0
        Rth = 0.5

        dt = calcul_echauffement_thermique(Ploss, Rth, clamp_non_negative=True)

        _log_info("calc | Ploss=%g | Rth=%g | clamp=True | dt=%g | attendu=0",
                  Ploss, Rth, dt)

        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    def test_offset_peut_rendre_positif_malgre_pertes_negatives(self) -> None:
        Ploss = -100.0
        Rth = 0.5  # -50
        offset = 60.0
        attendu = -50.0 + offset  # 10

        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset)

        _log_info("calc | Ploss=%g | Rth=%g | offset=%g | clamp=False | dt=%g | attendu=%g",
                  Ploss, Rth, offset, dt, attendu)

        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_offset_negatif_possible(self) -> None:
        Ploss = 100.0
        Rth = 0.5  # 50
        offset = -10.0
        attendu = 40.0

        dt = calcul_echauffement_thermique(Ploss, Rth, offset_temperature=offset)

        _log_info("calc | Ploss=%g | Rth=%g | offset=%g | dt=%g | attendu=%g",
                  Ploss, Rth, offset, dt, attendu)

        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_clamp_applique_apres_offset(self) -> None:
        Ploss = 10.0
        Rth = 0.1  # 1
        offset = -5.0  # => -4

        dt = calcul_echauffement_thermique(
            Ploss, Rth, offset_temperature=offset, clamp_non_negative=True
        )

        _log_info("calc | Ploss=%g | Rth=%g | offset=%g | clamp=True | dt=%g | attendu=0",
                  Ploss, Rth, offset, dt)

        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    # --------------------------
    # Rth négatif (autorisé par le module)
    # --------------------------

    def test_resistance_thermique_negative_autorisee(self) -> None:
        Ploss = 100.0
        Rth = -0.5
        attendu = -50.0

        dt = calcul_echauffement_thermique(Ploss, Rth)

        _log_info("calc | Rth négatif | Ploss=%g | Rth=%g | dt=%g | attendu=%g",
                  Ploss, Rth, dt, attendu)

        self.assertIsClose(dt, attendu, rel=0.0, abs_=0.0)

    def test_rth_negative_et_clamp(self) -> None:
        Ploss = 100.0
        Rth = -0.5  # dt=-50

        dt = calcul_echauffement_thermique(Ploss, Rth, clamp_non_negative=True)

        _log_info("calc | Rth négatif | clamp=True | Ploss=%g | Rth=%g | dt=%g | attendu=0",
                  Ploss, Rth, dt)

        self.assertIsClose(dt, 0.0, rel=0.0, abs_=0.0)

    # --------------------------
    # Non-finis (NaN/inf)
    # --------------------------

    def test_puissance_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | Ploss=NaN/inf")
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(float("nan"), 0.5)
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(float("inf"), 0.5)
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(float("-inf"), 0.5)

    def test_rth_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | Rth=NaN/inf")
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, float("nan"))
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, float("inf"))
        with self.assertRaises(ValueError):
            calcul_echauffement_thermique(100.0, float("-inf"))

    def test_offset_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | offset=NaN/inf")
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
        _log_info("calc | ints | Ploss=100 | Rth=1 | offset=0 | dt=%g | attendu=100", dt)
        self.assertIsClose(dt, 100.0, rel=0.0, abs_=0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
