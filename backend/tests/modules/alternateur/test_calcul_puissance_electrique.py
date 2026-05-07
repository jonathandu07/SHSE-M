# backend/tests/modules/alternateur/test_calcul_puissance_electrique.py

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

from backend.components.alternateur.modules.calcul_puissance_electrique import (
    calcul_puissance_dc,
    calcul_puissance_monophase,
    calcul_puissance_triphase,
)


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

    base = Path(__file__).stem  # ex: test_calcul_puissance_electrique
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


class TestCalculPuissanceElectrique(unittest.TestCase):
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

    # =========================================================================
    # Triphasé - entrée VLL/IL
    # =========================================================================

    def test_triphase_vll_il_pf1(self) -> None:
        VLL = 400.0
        IL = 10.0
        pf = 1.0
        S = math.sqrt(3.0) * VLL * IL
        attendu = S * pf

        P = calcul_puissance_triphase(VLL, IL, pf, entree="VLL_IL")

        _log_info("3ph VLL/IL | VLL=%g IL=%g pf=%g | P=%g | attendu=%g", VLL, IL, pf, P, attendu)
        self.assertIsInstance(P, float)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_triphase_vll_il_pf05(self) -> None:
        VLL = 400.0
        IL = 10.0
        pf = 0.5
        attendu = math.sqrt(3.0) * VLL * IL * pf

        P = calcul_puissance_triphase(VLL, IL, pf, entree="VLL_IL")

        _log_info("3ph VLL/IL | pf=0.5 | P=%g | attendu=%g", P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_triphase_vll_il_pf_negative(self) -> None:
        # pf<0 => P négative (convention), Q reste magnitude
        VLL = 400.0
        IL = 10.0
        pf = -0.8
        attendu = math.sqrt(3.0) * VLL * IL * pf

        P = calcul_puissance_triphase(VLL, IL, pf, entree="VLL_IL", clamp_non_negative=False)

        _log_info("3ph VLL/IL | pf=-0.8 | P=%g | attendu=%g", P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_triphase_clamp_non_negative(self) -> None:
        VLL = 400.0
        IL = 10.0
        pf = -0.8
        P = calcul_puissance_triphase(VLL, IL, pf, entree="VLL_IL", clamp_non_negative=True)
        _log_info("3ph clamp | pf=-0.8 | P=%g | attendu=0", P)
        self.assertIsClose(P, 0.0, rel=0.0, abs_=0.0)

    def test_triphase_return_details(self) -> None:
        VLL = 400.0
        IL = 10.0
        pf = 0.8
        out = calcul_puissance_triphase(VLL, IL, pf, entree="VLL_IL", return_details=True)
        self.assertIsInstance(out, dict)

        P = out["P"]
        S = out["S"]
        Q = out["Q"]

        S_att = math.sqrt(3.0) * VLL * IL
        P_att = S_att * max(-1.0, min(1.0, pf))
        sin_phi = math.sqrt(max(0.0, 1.0 - pf * pf))
        Q_att = S_att * sin_phi

        _log_info("3ph details | out=%r", out)
        self.assertIsClose(out["V_LL"], VLL, rel=0.0, abs_=0.0)
        self.assertIsClose(out["I_L"], IL, rel=0.0, abs_=0.0)
        self.assertIsClose(S, S_att, rel=1e-12)
        self.assertIsClose(P, P_att, rel=1e-12)
        self.assertIsClose(Q, Q_att, rel=1e-12)

    # =========================================================================
    # Triphasé - entrée Vph/Iph + connexion
    # =========================================================================

    def test_triphase_vph_iph_Y_equivalent(self) -> None:
        # Y : VLL = sqrt(3)*Vph ; IL = Iph
        Vph = 230.0
        Iph = 10.0
        pf = 0.9
        VLL = math.sqrt(3.0) * Vph
        IL = Iph
        attendu = math.sqrt(3.0) * VLL * IL * pf

        P = calcul_puissance_triphase(Vph, Iph, pf, entree="Vph_Iph", connexion="Y")
        _log_info("3ph Vph/Iph Y | P=%g | attendu=%g", P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_triphase_vph_iph_Delta_equivalent(self) -> None:
        # Delta : VLL = Vph ; IL = sqrt(3)*Iph
        Vph = 230.0
        Iph = 10.0
        pf = 0.9
        VLL = Vph
        IL = math.sqrt(3.0) * Iph
        attendu = math.sqrt(3.0) * VLL * IL * pf

        P = calcul_puissance_triphase(Vph, Iph, pf, entree="Vph_Iph", connexion="Delta")
        _log_info("3ph Vph/Iph Delta | P=%g | attendu=%g", P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_triphase_connexion_invalide_refuse(self) -> None:
        _log_info("expect ValueError | connexion invalide")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(230.0, 10.0, 1.0, entree="Vph_Iph", connexion="Z")  # type: ignore[arg-type]

    def test_triphase_entree_invalide_refuse(self) -> None:
        _log_info("expect ValueError | entree invalide")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(400.0, 10.0, 1.0, entree="XYZ")  # type: ignore[arg-type]

    # =========================================================================
    # Facteur de puissance (pf)
    # =========================================================================

    def test_pf_trop_grand_refuse(self) -> None:
        _log_info("expect ValueError | pf > 1")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(400.0, 10.0, 1.1)

    def test_pf_trop_petit_refuse(self) -> None:
        _log_info("expect ValueError | pf < -1")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(400.0, 10.0, -1.1)

    def test_pf_legere_survaleur_float_corregee(self) -> None:
        # tolérance interne: 1 + 5e-10 passe, sera clampé à 1.0
        pf = 1.0 + 5e-10
        out = calcul_puissance_triphase(400.0, 10.0, pf, return_details=True)
        self.assertIsInstance(out, dict)
        _log_info("pf survaleur | pf_in=%g pf_used=%g", pf, out["pf"])
        self.assertIsClose(out["pf"], 1.0, rel=0.0, abs_=0.0)

    def test_pf_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | pf NaN")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(400.0, 10.0, float("nan"))

    # =========================================================================
    # Non-finis (V/I)
    # =========================================================================

    def test_triphase_v_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | VLL NaN/inf")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(float("nan"), 10.0)
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(float("inf"), 10.0)

    def test_triphase_i_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | IL NaN/inf")
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(400.0, float("nan"))
        with self.assertRaises(ValueError):
            calcul_puissance_triphase(400.0, float("inf"))

    # =========================================================================
    # Monophasé
    # =========================================================================

    def test_monophase_nominal(self) -> None:
        V = 230.0
        I = 10.0
        pf = 0.8
        attendu = V * I * pf
        P = calcul_puissance_monophase(V, I, pf)

        _log_info("1ph | V=%g I=%g pf=%g | P=%g | attendu=%g", V, I, pf, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_monophase_details(self) -> None:
        V = 230.0
        I = 10.0
        pf = 0.6
        out = calcul_puissance_monophase(V, I, pf, return_details=True)
        self.assertIsInstance(out, dict)

        S = V * I
        P_att = S * pf
        Q_att = S * math.sqrt(max(0.0, 1.0 - pf * pf))

        _log_info("1ph details | out=%r", out)
        self.assertIsClose(out["S"], S, rel=1e-12)
        self.assertIsClose(out["P"], P_att, rel=1e-12)
        self.assertIsClose(out["Q"], Q_att, rel=1e-12)

    def test_monophase_pf_negatif_et_clamp(self) -> None:
        P = calcul_puissance_monophase(230.0, 10.0, -0.5, clamp_non_negative=True)
        _log_info("1ph clamp | pf=-0.5 | P=%g | attendu=0", P)
        self.assertIsClose(P, 0.0, rel=0.0, abs_=0.0)

    def test_monophase_v_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | V NaN")
        with self.assertRaises(ValueError):
            calcul_puissance_monophase(float("nan"), 10.0)

    def test_monophase_i_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | I inf")
        with self.assertRaises(ValueError):
            calcul_puissance_monophase(230.0, float("inf"))

    # =========================================================================
    # DC
    # =========================================================================

    def test_dc_nominal(self) -> None:
        V = 48.0
        I = 10.0
        attendu = V * I
        P = calcul_puissance_dc(V, I)
        _log_info("DC | V=%g I=%g | P=%g | attendu=%g", V, I, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_dc_negative_clamp(self) -> None:
        P = calcul_puissance_dc(48.0, -10.0, clamp_non_negative=True)
        _log_info("DC clamp | V=48 I=-10 | P=%g | attendu=0", P)
        self.assertIsClose(P, 0.0, rel=0.0, abs_=0.0)

    def test_dc_details(self) -> None:
        out = calcul_puissance_dc(48.0, 10.0, return_details=True)
        self.assertIsInstance(out, dict)
        _log_info("DC details | out=%r", out)
        self.assertIn("P", out)
        self.assertIn("V", out)
        self.assertIn("I", out)
        self.assertIsClose(out["P"], 480.0, rel=0.0, abs_=0.0)

    def test_dc_non_finis_refuse(self) -> None:
        _log_info("expect ValueError | V NaN")
        with self.assertRaises(ValueError):
            calcul_puissance_dc(float("nan"), 10.0)
        _log_info("expect ValueError | I inf")
        with self.assertRaises(ValueError):
            calcul_puissance_dc(48.0, float("inf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
