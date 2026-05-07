# backend/tests/modules/alternateur/test_calcul_frequence_synchrone.py

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

from backend.components.alternateur.modules.calcul_frequence_synchrone import *  # noqa: F403,F401


# =============================================================================
# LOGS (backend/logs/<nom_test>_YYYYMMDD_HHMMSS.log)
# =============================================================================

_LOGGER: Optional[logging.Logger] = None
_LOG_PATH: Optional[Path] = None


def _trouver_backend_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "backend":
            return parent
    return here.parents[3]


def _creer_logger_fichier() -> Tuple[logging.Logger, Path]:
    backend_dir = _trouver_backend_dir()
    logs_dir = backend_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    base = Path(__file__).stem  # ex: test_calcul_frequence_synchrone
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"{base}_{ts}.log"

    logger = logging.getLogger(f"backend.tests.{base}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Nettoyage handlers (évite doublons si re-run dans même process)
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
        logger.removeHandler(h)

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


class TestCalculFrequenceSynchrone(unittest.TestCase):
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

    # -------------------------------------------------------------------------
    # Cas nominaux (mode_poles='poles' / alias 'pair_poles')
    # -------------------------------------------------------------------------

    def test_poles_nominal(self) -> None:
        n_rpm = 3000.0
        P = 4  # pôles
        attendu = (n_rpm * P) / 120.0  # 100 Hz

        f = calcul_frequence_synchrone(n_rpm, P, mode_poles="poles")  # noqa: F405

        _log_info("calc | n_rpm=%g | P=%d | mode=poles | f=%g | attendu=%g", n_rpm, P, f, attendu)
        self.assertIsInstance(f, float)
        self.assertIsClose(f, attendu, rel=1e-12)

    def test_pair_poles_alias(self) -> None:
        n_rpm = 3000.0
        P = 4
        attendu = (n_rpm * P) / 120.0

        f = calcul_frequence_synchrone(n_rpm, P, mode_poles="pair_poles")  # noqa: F405

        _log_info("calc | n_rpm=%g | P=%d | mode=pair_poles | f=%g | attendu=%g", n_rpm, P, f, attendu)
        self.assertIsClose(f, attendu, rel=1e-12)

    def test_poles_impair_refuse(self) -> None:
        _log_info("expect ValueError | P impair en mode=poles")
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(3000.0, 3, mode_poles="poles")  # noqa: F405

    # -------------------------------------------------------------------------
    # Cas nominaux (mode_poles='pole_pairs')
    # -------------------------------------------------------------------------

    def test_pole_pairs_nominal(self) -> None:
        n_rpm = 3000.0
        p = 2  # paires de pôles
        attendu = (n_rpm * p) / 60.0  # 100 Hz

        f = calcul_frequence_synchrone(n_rpm, p, mode_poles="pole_pairs")  # noqa: F405

        _log_info("calc | n_rpm=%g | p=%d | mode=pole_pairs | f=%g | attendu=%g", n_rpm, p, f, attendu)
        self.assertIsClose(f, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # Signe / clamp
    # -------------------------------------------------------------------------

    def test_vitesse_negative_clamp_true(self) -> None:
        n_rpm = -3000.0
        P = 4
        attendu = abs((n_rpm * P) / 120.0)

        f = calcul_frequence_synchrone(n_rpm, P, mode_poles="poles", clamp_non_negative=True)  # noqa: F405
        _log_info("calc | n_rpm=%g | clamp=True | f=%g | attendu=%g", n_rpm, f, attendu)
        self.assertIsClose(f, attendu, rel=1e-12)

    def test_vitesse_negative_clamp_false(self) -> None:
        n_rpm = -3000.0
        P = 4
        attendu = (n_rpm * P) / 120.0  # négatif

        f = calcul_frequence_synchrone(n_rpm, P, mode_poles="poles", clamp_non_negative=False)  # noqa: F405
        _log_info("calc | n_rpm=%g | clamp=False | f=%g | attendu=%g", n_rpm, f, attendu)
        self.assertIsClose(f, attendu, rel=1e-12)

    def test_vitesse_zero_ok(self) -> None:
        f = calcul_frequence_synchrone(0.0, 4, mode_poles="poles")  # noqa: F405
        _log_info("calc | n_rpm=0 | P=4 | f=%g", f)
        self.assertIsClose(f, 0.0, rel=0.0, abs_=0.0)

    # -------------------------------------------------------------------------
    # Validations d'entrée (types / finitude / domaines)
    # -------------------------------------------------------------------------

    def test_vitesse_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | n_rpm NaN/inf")
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(float("nan"), 4)  # noqa: F405
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(float("inf"), 4)  # noqa: F405
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(float("-inf"), 4)  # noqa: F405

    def test_nombre_poles_non_int_refuse(self) -> None:
        _log_info("expect ValueError | nombre_poles non int")
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(3000.0, 4.0)  # type: ignore[arg-type]  # noqa: F405

    def test_nombre_poles_zero_ou_negatif_refuse(self) -> None:
        _log_info("expect ValueError | nombre_poles <= 0")
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(3000.0, 0)  # noqa: F405
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(3000.0, -2)  # noqa: F405

    def test_mode_poles_invalide_refuse(self) -> None:
        _log_info("expect ValueError | mode_poles invalide")
        with self.assertRaises(ValueError):
            calcul_frequence_synchrone(3000.0, 4, mode_poles="xyz")  # type: ignore[arg-type]  # noqa: F405

    # -------------------------------------------------------------------------
    # Cohérence équivalence (P=2p)
    # -------------------------------------------------------------------------

    def test_equivalence_poles_vs_pole_pairs(self) -> None:
        n_rpm = 1500.0
        p = 3
        P = 2 * p

        fP = calcul_frequence_synchrone(n_rpm, P, mode_poles="poles")  # noqa: F405
        fp = calcul_frequence_synchrone(n_rpm, p, mode_poles="pole_pairs")  # noqa: F405

        _log_info("equiv | n_rpm=%g | P=%d | p=%d | f(P)=%g | f(p)=%g", n_rpm, P, p, fP, fp)
        self.assertIsClose(fP, fp, rel=1e-12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
