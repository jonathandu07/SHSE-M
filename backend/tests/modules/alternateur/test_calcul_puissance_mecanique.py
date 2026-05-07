# backend/tests/modules/alternateur/test_calcul_puissance_mecanique.py

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

from backend.components.alternateur.modules.calcul_puissance_mecanique import calcul_puissance_mecanique


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

    base = Path(__file__).stem  # ex: test_calcul_puissance_mecanique
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


class TestCalculPuissanceMecanique(unittest.TestCase):
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
    # Cas nominaux
    # -------------------------------------------------------------------------

    def test_nominal_sans_pertes(self) -> None:
        P_e = 1000.0
        eta = 0.9
        attendu = P_e / eta

        Pm = calcul_puissance_mecanique(P_e, eta)

        _log_info("nominal | P_e=%g eta=%g -> Pm=%g attendu=%g", P_e, eta, Pm, attendu)
        self.assertIsInstance(Pm, float)
        self.assertIsClose(Pm, attendu, rel=1e-12)

    def test_nominal_avec_pertes(self) -> None:
        P_e = 1000.0
        pertes = 100.0
        eta = 0.9
        attendu = (P_e + pertes) / eta

        Pm = calcul_puissance_mecanique(P_e, eta, pertes_fixes_w=pertes)

        _log_info("avec pertes | P_e=%g pertes=%g eta=%g -> Pm=%g attendu=%g", P_e, pertes, eta, Pm, attendu)
        self.assertIsClose(Pm, attendu, rel=1e-12)

    def test_rendement_un(self) -> None:
        P_e = 250.0
        eta = 1.0
        attendu = 250.0

        Pm = calcul_puissance_mecanique(P_e, eta)
        _log_info("eta=1 | P_e=%g -> Pm=%g", P_e, Pm)
        self.assertIsClose(Pm, attendu, rel=0.0, abs_=0.0)

    # -------------------------------------------------------------------------
    # Signe / régénération
    # -------------------------------------------------------------------------

    def test_puissance_negative_conserver(self) -> None:
        P_e = -500.0
        eta = 0.8
        attendu = P_e / eta  # -625

        Pm = calcul_puissance_mecanique(P_e, eta, mode_signe="conserver")

        _log_info("regen conserver | P_e=%g eta=%g -> Pm=%g attendu=%g", P_e, eta, Pm, attendu)
        self.assertIsClose(Pm, attendu, rel=0.0, abs_=0.0)

    def test_puissance_negative_mode_abs(self) -> None:
        P_e = -500.0
        eta = 0.8
        attendu = abs(P_e / eta)  # 625

        Pm = calcul_puissance_mecanique(P_e, eta, mode_signe="abs")

        _log_info("regen abs | P_e=%g eta=%g -> Pm=%g attendu=%g", P_e, eta, Pm, attendu)
        self.assertIsClose(Pm, attendu, rel=0.0, abs_=0.0)

    def test_pertes_peuvent_inverser_le_signe(self) -> None:
        # P_e négatif mais pertes positives peuvent rendre (P_e+pertes) positif
        P_e = -50.0
        pertes = 100.0
        eta = 0.5
        attendu = (P_e + pertes) / eta  # 100

        Pm = calcul_puissance_mecanique(P_e, eta, pertes_fixes_w=pertes, mode_signe="conserver")

        _log_info("inversion signe | P_e=%g pertes=%g eta=%g -> Pm=%g attendu=%g", P_e, pertes, eta, Pm, attendu)
        self.assertIsClose(Pm, attendu, rel=0.0, abs_=0.0)

    # -------------------------------------------------------------------------
    # clamp_non_negative
    # -------------------------------------------------------------------------

    def test_clamp_force_zero_si_negatif(self) -> None:
        P_e = -500.0
        eta = 0.8
        Pm = calcul_puissance_mecanique(P_e, eta, clamp_non_negative=True, mode_signe="conserver")

        _log_info("clamp | P_e=%g eta=%g -> Pm=%g attendu=0", P_e, eta, Pm)
        self.assertIsClose(Pm, 0.0, rel=0.0, abs_=0.0)

    def test_clamp_ne_change_pas_si_positif(self) -> None:
        P_e = 500.0
        eta = 0.8
        attendu = P_e / eta

        Pm = calcul_puissance_mecanique(P_e, eta, clamp_non_negative=True)

        _log_info("clamp | P_e=%g eta=%g -> Pm=%g attendu=%g", P_e, eta, Pm, attendu)
        self.assertIsClose(Pm, attendu, rel=1e-12)

    def test_abs_puis_clamp(self) -> None:
        # mode_abs rend déjà positif ; clamp ne doit pas modifier
        P_e = -500.0
        eta = 0.8
        attendu = abs(P_e / eta)

        Pm = calcul_puissance_mecanique(P_e, eta, mode_signe="abs", clamp_non_negative=True)

        _log_info("abs+clamp | P_e=%g eta=%g -> Pm=%g attendu=%g", P_e, eta, Pm, attendu)
        self.assertIsClose(Pm, attendu, rel=0.0, abs_=0.0)

    # -------------------------------------------------------------------------
    # Validations : rendement
    # -------------------------------------------------------------------------

    def test_rendement_zero_refuse(self) -> None:
        _log_info("expect ValueError | eta=0")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, 0.0)

    def test_rendement_negatif_refuse(self) -> None:
        _log_info("expect ValueError | eta<0")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, -0.1)

    def test_rendement_superieur_un_refuse(self) -> None:
        _log_info("expect ValueError | eta>1")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, 1.0000001)

    def test_rendement_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | eta NaN/inf")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, float("nan"))
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, float("inf"))

    # -------------------------------------------------------------------------
    # Validations : puissance / pertes / mode_signe
    # -------------------------------------------------------------------------

    def test_puissance_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | P_e NaN/inf")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(float("nan"), 0.9)
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(float("inf"), 0.9)
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(float("-inf"), 0.9)

    def test_pertes_non_finies_refuse(self) -> None:
        _log_info("expect ValueError | pertes NaN/inf")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, 0.9, pertes_fixes_w=float("nan"))
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, 0.9, pertes_fixes_w=float("inf"))

    def test_mode_signe_invalide_refuse(self) -> None:
        _log_info("expect ValueError | mode_signe invalide")
        with self.assertRaises(ValueError):
            calcul_puissance_mecanique(100.0, 0.9, mode_signe="xyz")  # type: ignore[arg-type]

    # -------------------------------------------------------------------------
    # Types (int acceptés)
    # -------------------------------------------------------------------------

    def test_entiers_acceptes(self) -> None:
        Pm = calcul_puissance_mecanique(1000, 1)  # type: ignore[arg-type]
        _log_info("ints | Pm=%g attendu=1000", Pm)
        self.assertIsClose(Pm, 1000.0, rel=0.0, abs_=0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
