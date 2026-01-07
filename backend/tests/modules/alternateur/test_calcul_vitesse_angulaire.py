# backend/tests/modules/alternateur/test_calcul_vitesse_angulaire.py

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

from backend.modules.alternateur.calcul_vitesse_angulaire import calcul_vitesse_angulaire


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

    base = Path(__file__).stem  # ex: test_calcul_vitesse_angulaire
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


class TestCalculVitesseAngulaire(unittest.TestCase):
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
    # Nominal: rpm -> rad/s
    # -------------------------------------------------------------------------

    def test_rpm_zero_donne_zero(self) -> None:
        omega = calcul_vitesse_angulaire(0.0)
        _log_info("rpm=0 -> omega=%g", omega)
        self.assertIsClose(omega, 0.0, rel=0.0, abs_=0.0)

    def test_rpm_60_donne_2pi(self) -> None:
        # 60 rpm = 1 tr/s => omega = 2π
        omega = calcul_vitesse_angulaire(60.0)
        attendu = 2.0 * math.pi
        _log_info("rpm=60 -> omega=%g attendu=%g", omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    def test_rpm_120_donne_4pi(self) -> None:
        omega = calcul_vitesse_angulaire(120.0)
        attendu = 4.0 * math.pi
        _log_info("rpm=120 -> omega=%g attendu=%g", omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    def test_rpm_valeur_arbitraire(self) -> None:
        rpm = 3456.0
        omega = calcul_vitesse_angulaire(rpm)
        attendu = (2.0 * math.pi * rpm) / 60.0
        _log_info("rpm=%g -> omega=%g attendu=%g", rpm, omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # Signe / allow_negative / clamp_non_negative
    # -------------------------------------------------------------------------

    def test_rpm_negatif_autorise_par_defaut(self) -> None:
        rpm = -60.0
        omega = calcul_vitesse_angulaire(rpm, allow_negative=True, clamp_non_negative=False, input_unite="rpm")
        attendu = (2.0 * math.pi * rpm) / 60.0  # -2π
        _log_info("rpm=%g (neg) allow -> omega=%g attendu=%g", rpm, omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    def test_rpm_negatif_refuse_si_allow_negative_false(self) -> None:
        _log_info("expect ValueError | rpm negatif et allow_negative=False")
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(-1.0, allow_negative=False)

    def test_clamp_non_negative_force_valeur_absolue(self) -> None:
        rpm = -60.0
        omega = calcul_vitesse_angulaire(rpm, allow_negative=True, clamp_non_negative=True, input_unite="rpm")
        attendu = abs((2.0 * math.pi * rpm) / 60.0)  # 2π
        _log_info("rpm=%g clamp -> omega=%g attendu=%g", rpm, omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    def test_allow_negative_false_mais_rpm_positif_ok(self) -> None:
        rpm = 10.0
        omega = calcul_vitesse_angulaire(rpm, allow_negative=False)
        attendu = (2.0 * math.pi * rpm) / 60.0
        _log_info("rpm=%g allow_negative=False -> omega=%g attendu=%g", rpm, omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # input_unite="rad_s" (identité)
    # -------------------------------------------------------------------------

    def test_input_rad_s_identite(self) -> None:
        x = 123.456
        omega = calcul_vitesse_angulaire(x, input_unite="rad_s")
        _log_info("rad_s=%g -> omega=%g", x, omega)
        self.assertIsClose(omega, x, rel=0.0, abs_=0.0)

    def test_input_rad_s_negatif_autorise_par_defaut(self) -> None:
        x = -12.0
        omega = calcul_vitesse_angulaire(x, input_unite="rad_s", allow_negative=True)
        _log_info("rad_s=%g (neg) allow -> omega=%g", x, omega)
        self.assertIsClose(omega, x, rel=0.0, abs_=0.0)

    def test_input_rad_s_negatif_refuse_si_allow_negative_false(self) -> None:
        _log_info("expect ValueError | rad_s negatif et allow_negative=False")
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(-0.1, input_unite="rad_s", allow_negative=False)

    def test_input_rad_s_clamp_abs(self) -> None:
        x = -12.0
        omega = calcul_vitesse_angulaire(x, input_unite="rad_s", clamp_non_negative=True)
        _log_info("rad_s=%g clamp -> omega=%g attendu=%g", x, omega, abs(x))
        self.assertIsClose(omega, abs(x), rel=0.0, abs_=0.0)

    # -------------------------------------------------------------------------
    # Validations: NaN/inf et input_unite invalide
    # -------------------------------------------------------------------------

    def test_non_finis_refuses(self) -> None:
        _log_info("expect ValueError | NaN/inf")
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(float("nan"))
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(float("inf"))
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(float("-inf"))

    def test_input_unite_invalide_refuse(self) -> None:
        _log_info("expect ValueError | input_unite invalide")
        with self.assertRaises(ValueError):
            calcul_vitesse_angulaire(10.0, input_unite="xyz")  # type: ignore[arg-type]

    # -------------------------------------------------------------------------
    # Types: int acceptés
    # -------------------------------------------------------------------------

    def test_entiers_acceptes(self) -> None:
        omega = calcul_vitesse_angulaire(60)  # type: ignore[arg-type]
        attendu = 2.0 * math.pi
        _log_info("int rpm=60 -> omega=%g attendu=%g", omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
