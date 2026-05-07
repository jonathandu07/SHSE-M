# backend/tests/modules/alternateur/test_calcul_fem_induite.py

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

from backend.components.alternateur.modules.calcul_fem_induite import *  # noqa: F403,F401


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

    base = Path(__file__).stem  # ex: test_calcul_fem_induite
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


class TestCalculFEMInduite(unittest.TestCase):
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
    # Conversions
    # -------------------------------------------------------------------------

    def test_rpm_to_hz(self) -> None:
        hz = rpm_to_hz(1200.0)  # noqa: F405
        _log_info("rpm_to_hz | rpm=1200 -> hz=%g", hz)
        self.assertIsClose(hz, 20.0, rel=0.0, abs_=0.0)

    def test_hz_to_rpm(self) -> None:
        rpm = hz_to_rpm(20.0)  # noqa: F405
        _log_info("hz_to_rpm | hz=20 -> rpm=%g", rpm)
        self.assertIsClose(rpm, 1200.0, rel=0.0, abs_=0.0)

    def test_omega_to_hz(self) -> None:
        omega = 2.0 * math.pi * 50.0
        hz = omega_to_hz(omega)  # noqa: F405
        _log_info("omega_to_hz | omega=%g -> hz=%g", omega, hz)
        self.assertIsClose(hz, 50.0, rel=1e-12)

    def test_hz_to_omega(self) -> None:
        omega = hz_to_omega(50.0)  # noqa: F405
        attendu = 2.0 * math.pi * 50.0
        _log_info("hz_to_omega | hz=50 -> omega=%g (attendu=%g)", omega, attendu)
        self.assertIsClose(omega, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # Constantes RMS
    # -------------------------------------------------------------------------

    def test_constante_rms_sinus(self) -> None:
        c = constante_rms_par_forme("sinus")  # noqa: F405
        _log_info("constante | onde=sinus -> C=%g", c)
        self.assertIsClose(c, 4.44, rel=0.0, abs_=0.0)

    def test_constante_rms_carree(self) -> None:
        c = constante_rms_par_forme("carree")  # noqa: F405
        _log_info("constante | onde=carree -> C=%g", c)
        self.assertIsClose(c, 4.00, rel=0.0, abs_=0.0)

    def test_constante_rms_custom(self) -> None:
        c = constante_rms_par_forme("custom", constante_custom=5.0)  # noqa: F405
        _log_info("constante | onde=custom | C=%g", c)
        self.assertIsClose(c, 5.0, rel=0.0, abs_=0.0)

    def test_constante_rms_custom_manquante_refuse(self) -> None:
        _log_info("expect ValueError | onde=custom sans constante_custom")
        with self.assertRaises(ValueError):
            constante_rms_par_forme("custom")  # noqa: F405

    def test_constante_rms_onde_invalide_refuse(self) -> None:
        _log_info("expect ValueError | onde invalide")
        with self.assertRaises(ValueError):
            constante_rms_par_forme("xyz")  # type: ignore[arg-type]  # noqa: F405

    # -------------------------------------------------------------------------
    # Calcul FEM (direct)
    # -------------------------------------------------------------------------

    def test_calcul_fem_induite_nominal(self) -> None:
        f = 100.0
        N = 10
        phi = 0.01
        kw = 0.9
        attendu = 4.44 * f * float(N) * phi * kw  # 39.96

        E = calcul_fem_induite(f, N, phi, kw, onde="sinus", clamp_non_negative=True)  # noqa: F405

        _log_info(
            "calcul_fem_induite | f=%g | N=%d | phi=%g | kw=%g | onde=sinus | E=%g | attendu=%g",
            f,
            N,
            phi,
            kw,
            E,
            attendu,
        )
        self.assertIsInstance(E, float)
        self.assertIsClose(E, attendu, rel=1e-12)

    def test_calcul_fem_induite_phi_negative_clamp_true(self) -> None:
        f = 100.0
        N = 10
        phi = -0.01
        kw = 0.9
        attendu = abs(4.44 * f * float(N) * phi * kw)

        E = calcul_fem_induite(f, N, phi, kw, onde="sinus", clamp_non_negative=True)  # noqa: F405
        _log_info("phi négatif clamp=True | E=%g | attendu=%g", E, attendu)
        self.assertIsClose(E, attendu, rel=1e-12)

    def test_calcul_fem_induite_phi_negative_clamp_false(self) -> None:
        f = 100.0
        N = 10
        phi = -0.01
        kw = 0.9
        attendu = 4.44 * f * float(N) * phi * kw  # négatif

        E = calcul_fem_induite(f, N, phi, kw, onde="sinus", clamp_non_negative=False)  # noqa: F405
        _log_info("phi négatif clamp=False | E=%g | attendu=%g", E, attendu)
        self.assertIsClose(E, attendu, rel=1e-12)

    def test_calcul_fem_induite_frequence_zero(self) -> None:
        E = calcul_fem_induite(0.0, 10, 0.01, 0.9)  # noqa: F405
        _log_info("f=0 -> E=%g", E)
        self.assertIsClose(E, 0.0, rel=0.0, abs_=0.0)

    def test_calcul_fem_induite_spires_zero(self) -> None:
        E = calcul_fem_induite(100.0, 0, 0.01, 0.9)  # noqa: F405
        _log_info("N=0 -> E=%g", E)
        self.assertIsClose(E, 0.0, rel=0.0, abs_=0.0)

    def test_calcul_fem_induite_custom_sans_constante_refuse(self) -> None:
        _log_info("expect ValueError | onde=custom sans constante_custom")
        with self.assertRaises(ValueError):
            calcul_fem_induite(100.0, 10, 0.01, 0.9, onde="custom")  # noqa: F405

    def test_calcul_fem_induite_validation_types(self) -> None:
        _log_info("expect ValueError | N non int")
        with self.assertRaises(ValueError):
            calcul_fem_induite(100.0, 10.5, 0.01, 0.9)  # type: ignore[arg-type]  # noqa: F405

        _log_info("expect ValueError | f=NaN")
        with self.assertRaises(ValueError):
            calcul_fem_induite(float("nan"), 10, 0.01, 0.9)  # noqa: F405

        _log_info("expect ValueError | phi=inf")
        with self.assertRaises(ValueError):
            calcul_fem_induite(100.0, 10, float("inf"), 0.9)  # noqa: F405

        _log_info("expect ValueError | kw=NaN")
        with self.assertRaises(ValueError):
            calcul_fem_induite(100.0, 10, 0.01, float("nan"))  # noqa: F405

    # -------------------------------------------------------------------------
    # Flux pôle + FEM via induction
    # -------------------------------------------------------------------------

    def test_calcul_flux_pole_mode_BA(self) -> None:
        phi = calcul_flux_pole(-0.8, 0.01, flux_model="B*A")  # noqa: F405
        _log_info("flux | B=-0.8 | A=0.01 | model=B*A -> phi=%g", phi)
        self.assertIsClose(phi, -0.008, rel=1e-12)

    def test_calcul_flux_pole_mode_absBA(self) -> None:
        phi = calcul_flux_pole(-0.8, 0.01, flux_model="abs(B)*A")  # noqa: F405
        _log_info("flux | B=-0.8 | A=0.01 | model=abs(B)*A -> phi=%g", phi)
        self.assertIsClose(phi, 0.008, rel=1e-12)

    def test_calcul_flux_pole_mode_invalide_refuse(self) -> None:
        _log_info("expect ValueError | flux_model invalide")
        with self.assertRaises(ValueError):
            calcul_flux_pole(0.8, 0.01, flux_model="xyz")  # type: ignore[arg-type]  # noqa: F405

    def test_calcul_fem_avec_induction_equivalence(self) -> None:
        f = 100.0
        N = 10
        B = 0.8
        A = 0.01
        kw = 0.9

        phi = calcul_flux_pole(B, A, flux_model="B*A")  # noqa: F405
        attendu = calcul_fem_induite(f, N, phi, kw, onde="sinus", clamp_non_negative=True)  # noqa: F405
        E = calcul_fem_induite_avec_induction(  # noqa: F405
            frequence_hz=f,
            nombre_spires_serie=N,
            induction_gap_t=B,
            aire_pole_m2=A,
            facteur_enroulement_kw=kw,
            onde="sinus",
            clamp_non_negative=True,
            flux_model="B*A",
        )

        _log_info("fem_avec_induction | phi=%g | E=%g | attendu=%g", phi, E, attendu)
        self.assertIsClose(E, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # Conversions phase/ligne
    # -------------------------------------------------------------------------

    def test_tension_ligne_depuis_phase(self) -> None:
        Vph = 100.0
        Vline_y = tension_ligne_depuis_phase(Vph, "etoile")  # noqa: F405
        Vline_d = tension_ligne_depuis_phase(Vph, "triangle")  # noqa: F405

        _log_info("Vligne | Vph=%g | etoile=%g | triangle=%g", Vph, Vline_y, Vline_d)
        self.assertIsClose(Vline_y, math.sqrt(3.0) * Vph, rel=1e-12)
        self.assertIsClose(Vline_d, Vph, rel=0.0, abs_=0.0)

    def test_tension_phase_depuis_ligne(self) -> None:
        Vl = 173.20508075688772  # ~= 100*sqrt(3)
        Vph = tension_phase_depuis_ligne(Vl, "etoile")  # noqa: F405
        _log_info("Vphase | Vl=%g | etoile -> Vph=%g", Vl, Vph)
        self.assertIsClose(Vph, Vl / math.sqrt(3.0), rel=1e-12)

        Vph2 = tension_phase_depuis_ligne(Vl, "triangle")  # noqa: F405
        _log_info("Vphase | Vl=%g | triangle -> Vph=%g", Vl, Vph2)
        self.assertIsClose(Vph2, Vl, rel=0.0, abs_=0.0)

    def test_tension_couplage_invalide_refuse(self) -> None:
        _log_info("expect ValueError | couplage invalide")
        with self.assertRaises(ValueError):
            tension_ligne_depuis_phase(100.0, "xyz")  # type: ignore[arg-type]  # noqa: F405
        with self.assertRaises(ValueError):
            tension_phase_depuis_ligne(100.0, "xyz")  # type: ignore[arg-type]  # noqa: F405

    # -------------------------------------------------------------------------
    # Fréquence <-> rpm (paires de pôles)
    # -------------------------------------------------------------------------

    def test_frequence_depuis_rpm(self) -> None:
        f = calcul_frequence_depuis_rpm(3000.0, 2)  # noqa: F405
        _log_info("f_depuis_rpm | rpm=3000 | p=2 -> f=%g", f)
        self.assertIsClose(f, 100.0, rel=0.0, abs_=0.0)

    def test_rpm_depuis_frequence(self) -> None:
        rpm = calcul_rpm_depuis_frequence(100.0, 2)  # noqa: F405
        _log_info("rpm_depuis_f | f=100 | p=2 -> rpm=%g", rpm)
        self.assertIsClose(rpm, 3000.0, rel=0.0, abs_=0.0)

    # -------------------------------------------------------------------------
    # Inverses utiles
    # -------------------------------------------------------------------------

    def test_calcul_spires_depuis_tension_arrondis(self) -> None:
        E = 100.0
        f = 100.0
        phi = 0.01
        kw = 0.9
        denom = 4.44 * f * phi * kw  # 3.996
        n_float = E / denom  # ~25.025...

        n_floor = calcul_spires_depuis_tension(E, f, phi, kw, arrondi="floor")  # noqa: F405
        n_ceil = calcul_spires_depuis_tension(E, f, phi, kw, arrondi="ceil")  # noqa: F405
        n_round = calcul_spires_depuis_tension(E, f, phi, kw, arrondi="round")  # noqa: F405

        _log_info(
            "spires_depuis_tension | E=%g f=%g phi=%g kw=%g | denom=%g | n_float=%g | floor=%d ceil=%d round=%d",
            E,
            f,
            phi,
            kw,
            denom,
            n_float,
            n_floor,
            n_ceil,
            n_round,
        )
        self.assertEqual(n_floor, 25)
        self.assertEqual(n_ceil, 26)
        self.assertEqual(n_round, 25)

    def test_calcul_spires_depuis_tension_division_par_zero_refuse(self) -> None:
        _log_info("expect ValueError | denom=0 via phi=0")
        with self.assertRaises(ValueError):
            calcul_spires_depuis_tension(100.0, 100.0, 0.0, 0.9, arrondi="ceil")  # noqa: F405

    def test_calcul_flux_depuis_tension(self) -> None:
        E = 100.0
        f = 100.0
        N = 40
        kw = 0.9
        C = 4.44
        attendu = E / (C * f * float(N) * kw)

        phi = calcul_flux_depuis_tension(E, f, N, kw, onde="sinus")  # noqa: F405
        _log_info("flux_depuis_tension | phi=%g | attendu=%g", phi, attendu)
        self.assertIsClose(phi, attendu, rel=1e-12)

    def test_calcul_kw_depuis_tension(self) -> None:
        E = 100.0
        f = 100.0
        N = 40
        phi = 0.01
        C = 4.44
        attendu = E / (C * f * float(N) * phi)

        kw = calcul_facteur_enroulement_depuis_tension(E, f, N, phi, onde="sinus")  # noqa: F405
        _log_info("kw_depuis_tension | kw=%g | attendu=%g", kw, attendu)
        self.assertIsClose(kw, attendu, rel=1e-12)

    # -------------------------------------------------------------------------
    # RapportFEM
    # -------------------------------------------------------------------------

    def test_rapport_fem_complet_rpm_et_induction(self) -> None:
        r = RapportFEM().generer(  # noqa: F405
            rpm_mecanique=3000.0,
            nb_paires_poles=2,
            induction_gap_t=0.8,
            aire_pole_m2=0.01,
            nombre_spires_serie=10,
            facteur_enroulement_kw=0.9,
            couplage="etoile",
            onde="sinus",
            flux_model="B*A",
            clamp_non_negative=True,
        )
        _log_info("rapport | resultats=%r", r.get("resultats"))
        self.assertIn("resultats", r)
        self.assertIn("inconnues", r)
        self.assertIn("E_phase_rms_V", r["resultats"])
        self.assertIn("V_ligne_rms_V", r["resultats"])
        self.assertIsInstance(r["resultats"]["E_phase_rms_V"], float)

    def test_rapport_fem_parametres_manquants(self) -> None:
        r = RapportFEM().generer(  # noqa: F405
            nombre_spires_serie=10,
            facteur_enroulement_kw=0.9,
        )
        _log_info("rapport incomplet | inconnues=%r", r.get("inconnues"))
        self.assertIn("inconnues", r)
        self.assertIn("impossibles", r["inconnues"])
        self.assertTrue(any(x.get("nom") == "frequence_hz" for x in r["inconnues"]["impossibles"]))
        self.assertTrue(any(x.get("nom") == "flux_max_pole_wb" for x in r["inconnues"]["impossibles"]))

    def test_rapport_fem_custom_sans_constante_refuse(self) -> None:
        _log_info("expect ValueError | rapport onde=custom sans constante_custom")
        with self.assertRaises(ValueError):
            RapportFEM().generer(  # noqa: F405
                frequence_hz=100.0,
                flux_max_pole_wb=0.01,
                nombre_spires_serie=10,
                facteur_enroulement_kw=0.9,
                onde="custom",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
