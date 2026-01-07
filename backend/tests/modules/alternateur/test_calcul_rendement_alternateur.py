# backend/tests/modules/alternateur/test_calcul_rendement_alternateur.py

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

from backend.modules.alternateur.calcul_rendement_alternateur import calcul_rendement_alternateur


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

    base = Path(__file__).stem  # ex: test_calcul_rendement_alternateur
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


class TestCalculRendementAlternateur(unittest.TestCase):
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
    # Cas nominaux (somme_pertes)
    # -------------------------------------------------------------------------

    def test_nominal_sans_pertes(self) -> None:
        P_out = 1000.0
        pertes = 0.0
        attendu = 1.0  # P_out / (P_out+0)
        eta = calcul_rendement_alternateur(P_out, somme_pertes=pertes)
        _log_info("nominal sans pertes | P_out=%g pertes=%g -> eta=%g", P_out, pertes, eta)
        self.assertIsInstance(eta, float)
        self.assertIsClose(eta, attendu, rel=0.0, abs_=0.0)

    def test_nominal_avec_pertes(self) -> None:
        P_out = 1000.0
        pertes = 250.0
        attendu = P_out / (P_out + pertes)
        eta = calcul_rendement_alternateur(P_out, somme_pertes=pertes)
        _log_info("nominal | P_out=%g pertes=%g -> eta=%g attendu=%g", P_out, pertes, eta, attendu)
        self.assertIsClose(eta, attendu, rel=1e-12)

    def test_clamp_0_1_par_defaut(self) -> None:
        # cas atypique: pertes négatives => eta > 1 si non clamp
        P_out = 1000.0
        pertes = -100.0  # P_in = 900 => eta = 1.111...
        eta = calcul_rendement_alternateur(P_out, somme_pertes=pertes, clamp_0_1=True)
        _log_info("clamp defaut | P_out=%g pertes=%g -> eta=%g (attendu clamp=1)", P_out, pertes, eta)
        self.assertIsClose(eta, 1.0, rel=0.0, abs_=0.0)

    def test_sans_clamp_peut_depasse_un(self) -> None:
        P_out = 1000.0
        pertes = -100.0
        attendu = P_out / (P_out + pertes)  # 1.111...
        eta = calcul_rendement_alternateur(P_out, somme_pertes=pertes, clamp_0_1=False)
        _log_info("sans clamp | eta=%g attendu=%g", eta, attendu)
        self.assertIsClose(eta, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # liste_pertes prioritaire (y compris vide)
    # -------------------------------------------------------------------------

    def test_liste_pertes_prioritaire(self) -> None:
        P_out = 1000.0
        somme_pertes = 9999.0  # ne doit pas être utilisée
        liste = [100.0, 150.0]
        pertes = sum(liste)
        attendu = P_out / (P_out + pertes)

        eta = calcul_rendement_alternateur(P_out, somme_pertes=somme_pertes, liste_pertes=liste)

        _log_info("liste prioritaire | liste=%r somme_pertes=%g -> eta=%g attendu=%g", liste, somme_pertes, eta, attendu)
        self.assertIsClose(eta, attendu, rel=1e-12)

    def test_liste_pertes_vide_donne_pertes_zero(self) -> None:
        P_out = 1000.0
        somme_pertes = 250.0  # doit être ignorée puisque liste fournie (même vide)
        eta = calcul_rendement_alternateur(P_out, somme_pertes=somme_pertes, liste_pertes=[])
        _log_info("liste vide | eta=%g attendu=1", eta)
        self.assertIsClose(eta, 1.0, rel=0.0, abs_=0.0)

    def test_ignore_none_in_list_true(self) -> None:
        P_out = 1000.0
        liste = [100.0, None, 50.0]  # type: ignore[list-item]
        pertes = 150.0
        attendu = P_out / (P_out + pertes)

        eta = calcul_rendement_alternateur(P_out, liste_pertes=liste, ignore_none_in_list=True)

        _log_info("ignore None | liste=%r -> eta=%g attendu=%g", liste, eta, attendu)
        self.assertIsClose(eta, attendu, rel=1e-12)

    def test_ignore_none_in_list_false_refuse(self) -> None:
        P_out = 1000.0
        liste = [100.0, None, 50.0]  # type: ignore[list-item]
        _log_info("expect ValueError | None dans liste_pertes et ignore_none_in_list=False")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(P_out, liste_pertes=liste, ignore_none_in_list=False)

    def test_liste_element_non_fini_refuse(self) -> None:
        P_out = 1000.0
        _log_info("expect ValueError | liste_pertes NaN")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(P_out, liste_pertes=[100.0, float("nan")])

    # -------------------------------------------------------------------------
    # reject_negative_losses
    # -------------------------------------------------------------------------

    def test_reject_negative_losses_somme(self) -> None:
        _log_info("expect ValueError | somme_pertes negative reject=True")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(1000.0, somme_pertes=-1.0, reject_negative_losses=True)

    def test_reject_negative_losses_liste(self) -> None:
        _log_info("expect ValueError | liste_pertes negative reject=True")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(1000.0, liste_pertes=[100.0, -1.0], reject_negative_losses=True)

    def test_negative_losses_acceptes_si_reject_false(self) -> None:
        P_out = 1000.0
        losses = [100.0, -10.0]
        # P_in = 1090 -> eta ~ 0.917431...
        attendu = P_out / (P_out + sum(losses))
        eta = calcul_rendement_alternateur(P_out, liste_pertes=losses, reject_negative_losses=False, clamp_0_1=False)
        _log_info("losses neg ok | losses=%r -> eta=%g attendu=%g", losses, eta, attendu)
        self.assertIsClose(eta, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # epsilon (anti-division / cas dégénéré)
    # -------------------------------------------------------------------------

    def test_pin_zero_renvoie_zero(self) -> None:
        # P_in = P_out + pertes = 0
        eta = calcul_rendement_alternateur(0.0, somme_pertes=0.0, epsilon=1e-12)
        _log_info("P_in=0 | eta=%g attendu=0", eta)
        self.assertIsClose(eta, 0.0, rel=0.0, abs_=0.0)

    def test_pin_tres_petit_<=epsilon_renvoie_zero(self) -> None:
        # P_in=1e-13 <= 1e-12 => 0
        eta = calcul_rendement_alternateur(1e-13, somme_pertes=0.0, epsilon=1e-12)
        _log_info("P_in<=epsilon | eta=%g attendu=0", eta)
        self.assertIsClose(eta, 0.0, rel=0.0, abs_=0.0)

    def test_pin_juste_au_dessus_epsilon_calcule(self) -> None:
        # P_in = 2e-12 > 1e-12 => calc
        P_out = 2e-12
        eta = calcul_rendement_alternateur(P_out, somme_pertes=0.0, epsilon=1e-12)
        _log_info("P_in>epsilon | eta=%g attendu=1", eta)
        self.assertIsClose(eta, 1.0, rel=0.0, abs_=0.0)

    def test_epsilon_invalide_refuse(self) -> None:
        _log_info("expect ValueError | epsilon negatif / NaN")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(1000.0, somme_pertes=100.0, epsilon=-1.0)
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(1000.0, somme_pertes=100.0, epsilon=float("nan"))

    # -------------------------------------------------------------------------
    # return_details
    # -------------------------------------------------------------------------

    def test_return_details(self) -> None:
        P_out = 1000.0
        liste = [100.0, 50.0]
        P_losses = 150.0
        P_in = 1150.0
        eta_att = P_out / P_in

        out = calcul_rendement_alternateur(P_out, liste_pertes=liste, return_details=True, clamp_0_1=False)
        self.assertIsInstance(out, dict)

        _log_info("details | out=%r", out)
        self.assertIn("eta", out)
        self.assertIn("P_out", out)
        self.assertIn("P_losses", out)
        self.assertIn("P_in", out)

        self.assertIsClose(out["P_out"], P_out, rel=0.0, abs_=0.0)
        self.assertIsClose(out["P_losses"], P_losses, rel=0.0, abs_=0.0)
        self.assertIsClose(out["P_in"], P_in, rel=0.0, abs_=0.0)
        self.assertIsClose(out["eta"], eta_att, rel=1e-12)

    # -------------------------------------------------------------------------
    # Non-finis (NaN/inf) + types
    # -------------------------------------------------------------------------

    def test_p_out_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | P_out NaN/inf")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(float("nan"))
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(float("inf"))

    def test_somme_pertes_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | somme_pertes NaN/inf")
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(1000.0, somme_pertes=float("nan"))
        with self.assertRaises(ValueError):
            calcul_rendement_alternateur(1000.0, somme_pertes=float("inf"))

    def test_entiers_acceptes(self) -> None:
        eta = calcul_rendement_alternateur(1000, somme_pertes=250)  # type: ignore[arg-type]
        attendu = 1000.0 / 1250.0
        _log_info("ints | eta=%g attendu=%g", eta, attendu)
        self.assertIsClose(eta, attendu, rel=1e-12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
