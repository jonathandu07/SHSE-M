# backend/tests/modules/alternateur/test_calcul_pertes_cuivre.py

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

from backend.modules.alternateur.calcul_pertes_cuivre import (
    calcul_pertes_cuivre_phase,
    calcul_pertes_cuivre_triphase,
    calcul_resistance_enroulement,
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

    base = Path(__file__).stem  # ex: test_calcul_pertes_cuivre
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


class TestCalculPertesCuivre(unittest.TestCase):
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
    # calcul_resistance_enroulement
    # =========================================================================

    def test_resistance_nominale_sans_temperature(self) -> None:
        # R = rho*L/A
        rho = 1.68e-8  # ohm·m (cuivre ~20°C, valeur d'exemple)
        L = 10.0
        A = 1.0e-6
        attendu = rho * L / A  # 0.168

        R = calcul_resistance_enroulement(rho, L, A)

        _log_info("R | rho=%g | L=%g | A=%g | R=%g | attendu=%g", rho, L, A, R, attendu)
        self.assertIsInstance(R, float)
        self.assertIsClose(R, attendu, rel=1e-12)

    def test_resistance_avec_temperature(self) -> None:
        rho_ref = 1.68e-8
        L = 10.0
        A = 1.0e-6
        T = 80.0
        Tref = 20.0
        alpha = 0.00393
        rho_T = rho_ref * (1.0 + alpha * (T - Tref))
        attendu = rho_T * L / A

        R = calcul_resistance_enroulement(
            rho_ref, L, A, temperature_c=T, temperature_ref_c=Tref, coef_temperature=alpha
        )

        _log_info(
            "R(T) | rho_ref=%g | T=%g | Tref=%g | alpha=%g | rho_T=%g | R=%g | attendu=%g",
            rho_ref,
            T,
            Tref,
            alpha,
            rho_T,
            R,
            attendu,
        )
        self.assertIsClose(R, attendu, rel=1e-12)

    def test_resistance_temperature_permet_rho_negatif_si_alpha_grand_et_T_basse_clamp_true(self) -> None:
        # Cas mathématique : rho(T) peut devenir négatif si (1+alpha*(T-Tref))<0
        rho_ref = 1.0
        L = 1.0
        A = 1.0
        T = 0.0
        Tref = 20.0
        alpha = 0.1  # => 1 + 0.1*(0-20)= -1

        R = calcul_resistance_enroulement(
            rho_ref, L, A, temperature_c=T, temperature_ref_c=Tref, coef_temperature=alpha, clamp_non_negative=True
        )

        _log_info("R clamp | rho_ref=%g | T=%g | Tref=%g | alpha=%g | R=%g | attendu=0", rho_ref, T, Tref, alpha, R)
        self.assertIsClose(R, 0.0, rel=0.0, abs_=0.0)

    def test_resistance_temperature_rho_negatif_si_clamp_false(self) -> None:
        rho_ref = 1.0
        L = 1.0
        A = 1.0
        T = 0.0
        Tref = 20.0
        alpha = 0.1  # facteur -1 => rho_T = -1

        attendu = -1.0  # rho_T * L / A

        R = calcul_resistance_enroulement(
            rho_ref, L, A, temperature_c=T, temperature_ref_c=Tref, coef_temperature=alpha, clamp_non_negative=False
        )

        _log_info("R unclamped | attendu=%g | R=%g", attendu, R)
        self.assertIsClose(R, attendu, rel=0.0, abs_=0.0)

    def test_resistance_section_zero_refuse(self) -> None:
        _log_info("expect ValueError | section_fil=0")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(1.0, 1.0, 0.0)

    def test_resistance_entrees_non_finies_refuse(self) -> None:
        _log_info("expect ValueError | rho NaN/inf")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(float("nan"), 1.0, 1.0)
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(float("inf"), 1.0, 1.0)

        _log_info("expect ValueError | L NaN")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(1.0, float("nan"), 1.0)

        _log_info("expect ValueError | A inf")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(1.0, 1.0, float("inf"))

    def test_resistance_temperature_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | temperature_c NaN")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(1.0, 1.0, 1.0, temperature_c=float("nan"))
        _log_info("expect ValueError | temperature_ref_c inf")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(1.0, 1.0, 1.0, temperature_c=20.0, temperature_ref_c=float("inf"))
        _log_info("expect ValueError | coef_temperature NaN")
        with self.assertRaises(ValueError):
            calcul_resistance_enroulement(1.0, 1.0, 1.0, temperature_c=20.0, coef_temperature=float("nan"))

    def test_resistance_rho_L_peuvent_etre_zero(self) -> None:
        # strict=False pour rho et L
        R = calcul_resistance_enroulement(0.0, 0.0, 1.0)
        _log_info("R | rho=0 L=0 A=1 -> R=%g", R)
        self.assertIsClose(R, 0.0, rel=0.0, abs_=0.0)

    # =========================================================================
    # calcul_pertes_cuivre_phase
    # =========================================================================

    def test_pertes_phase_rms_nominal(self) -> None:
        I = 10.0
        R = 0.5
        attendu = (I ** 2) * R  # 50

        P = calcul_pertes_cuivre_phase(I, R, courant_type="rms")

        _log_info("P_phase | I_rms=%g | R=%g | P=%g | attendu=%g", I, R, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_phase_peak_conversion(self) -> None:
        Ipk = 10.0
        R = 0.5
        Irms = Ipk / math.sqrt(2.0)
        attendu = (Irms ** 2) * R

        P = calcul_pertes_cuivre_phase(Ipk, R, courant_type="peak")

        _log_info("P_phase | I_peak=%g -> Irms=%g | R=%g | P=%g | attendu=%g", Ipk, Irms, R, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_phase_resistance_negative_autorisee_mathematiquement(self) -> None:
        # resistance strict=False => R peut être négatif ; clamp_non_negative protège par défaut
        I = 10.0
        R = -0.5
        P = calcul_pertes_cuivre_phase(I, R, clamp_non_negative=True)

        _log_info("P_phase clamp | I=%g | R=%g | P=%g | attendu=0", I, R, P)
        self.assertIsClose(P, 0.0, rel=0.0, abs_=0.0)

    def test_pertes_phase_resistance_negative_si_clamp_false(self) -> None:
        I = 10.0
        R = -0.5
        attendu = (I ** 2) * R  # -50

        P = calcul_pertes_cuivre_phase(I, R, clamp_non_negative=False)

        _log_info("P_phase unclamped | I=%g | R=%g | P=%g | attendu=%g", I, R, P, attendu)
        self.assertIsClose(P, attendu, rel=0.0, abs_=0.0)

    def test_pertes_phase_courant_type_invalide_refuse(self) -> None:
        _log_info("expect ValueError | courant_type invalide")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_phase(10.0, 0.5, courant_type="xyz")  # type: ignore[arg-type]

    def test_pertes_phase_courant_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | I NaN")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_phase(float("nan"), 0.5)

    def test_pertes_phase_resistance_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | R inf")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_phase(10.0, float("inf"))

    # =========================================================================
    # calcul_pertes_cuivre_triphase
    # =========================================================================

    def test_pertes_triphase_base_rms(self) -> None:
        Iph = 10.0
        Rph = 0.5
        attendu = 3.0 * (Iph ** 2) * Rph  # 150

        P = calcul_pertes_cuivre_triphase(Iph, Rph, courant_type="rms", courant_est_ligne=False)

        _log_info("P_3ph | Iph=%g | Rph=%g | P=%g | attendu=%g", Iph, Rph, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_triphase_peak_conversion(self) -> None:
        Ipk = 10.0
        Rph = 0.5
        Iph_rms = Ipk / math.sqrt(2.0)
        attendu = 3.0 * (Iph_rms ** 2) * Rph

        P = calcul_pertes_cuivre_triphase(Ipk, Rph, courant_type="peak", courant_est_ligne=False)

        _log_info("P_3ph | Ipk=%g -> Irms=%g | Rph=%g | P=%g | attendu=%g", Ipk, Iph_rms, Rph, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_triphase_courant_ligne_Y(self) -> None:
        Il = 10.0
        Rph = 0.5
        # Y: Iphase = Il
        attendu = 3.0 * (Il ** 2) * Rph

        P = calcul_pertes_cuivre_triphase(Il, Rph, courant_est_ligne=True, connexion="Y")

        _log_info("P_3ph | Iligne=%g | conn=Y -> Iph=%g | P=%g | attendu=%g", Il, Il, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_triphase_courant_ligne_Delta(self) -> None:
        Il = 10.0
        Rph = 0.5
        # Delta: Iphase = Il/sqrt(3)
        Iph = Il / math.sqrt(3.0)
        attendu = 3.0 * (Iph ** 2) * Rph

        P = calcul_pertes_cuivre_triphase(Il, Rph, courant_est_ligne=True, connexion="Delta")

        _log_info("P_3ph | Iligne=%g | conn=Delta -> Iph=%g | P=%g | attendu=%g", Il, Iph, P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_triphase_connexion_invalide_refuse_si_courant_ligne(self) -> None:
        _log_info("expect ValueError | connexion invalide quand courant_est_ligne=True")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_triphase(10.0, 0.5, courant_est_ligne=True, connexion="Z")  # type: ignore[arg-type]

    def test_pertes_triphase_connexion_ignores_si_pas_courant_ligne(self) -> None:
        # connexion n'est utilisée que si courant_est_ligne=True.
        Iph = 10.0
        Rph = 0.5
        attendu = 3.0 * (Iph ** 2) * Rph
        P = calcul_pertes_cuivre_triphase(Iph, Rph, courant_est_ligne=False, connexion="Z")  # type: ignore[arg-type]
        _log_info("P_3ph | courant_est_ligne=False | connexion ignorée | P=%g | attendu=%g", P, attendu)
        self.assertIsClose(P, attendu, rel=1e-12)

    def test_pertes_triphase_courant_type_invalide_refuse(self) -> None:
        _log_info("expect ValueError | courant_type invalide")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_triphase(10.0, 0.5, courant_type="xyz")  # type: ignore[arg-type]

    def test_pertes_triphase_resistance_negative_clamp_true(self) -> None:
        Iph = 10.0
        Rph = -0.5
        P = calcul_pertes_cuivre_triphase(Iph, Rph, clamp_non_negative=True)
        _log_info("P_3ph clamp | Iph=%g | Rph=%g | P=%g | attendu=0", Iph, Rph, P)
        self.assertIsClose(P, 0.0, rel=0.0, abs_=0.0)

    def test_pertes_triphase_resistance_negative_clamp_false(self) -> None:
        Iph = 10.0
        Rph = -0.5
        attendu = 3.0 * (Iph ** 2) * Rph  # -150
        P = calcul_pertes_cuivre_triphase(Iph, Rph, clamp_non_negative=False)
        _log_info("P_3ph unclamped | P=%g | attendu=%g", P, attendu)
        self.assertIsClose(P, attendu, rel=0.0, abs_=0.0)

    def test_pertes_triphase_courant_non_fini_refuse(self) -> None:
        _log_info("expect ValueError | courant_phase NaN")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_triphase(float("nan"), 0.5)

    def test_pertes_triphase_resistance_non_finie_refuse(self) -> None:
        _log_info("expect ValueError | resistance_phase NaN")
        with self.assertRaises(ValueError):
            calcul_pertes_cuivre_triphase(10.0, float("nan"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
