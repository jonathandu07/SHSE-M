# backend/tests/pieces/test_cylindre.py

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

from backend.pieces.cylindre import (
    Cylindre,
    EntreeConvectionTube,
    calcul_h_depuis_entree_convection,
)

# (optionnel) pour tests conditionnels (selon disponibilité des modules)
from backend.pieces import cylindre as cyl_mod


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
    # fallback très permissif
    return here.parents[3]


def _creer_logger_fichier() -> Tuple[logging.Logger, Path]:
    backend_dir = _trouver_backend_dir()
    logs_dir = backend_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    base = Path(__file__).stem  # ex: test_cylindre
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


class TestCylindre(unittest.TestCase):
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

    def assertIsClose(self, a: float, b: float, *, rel: float = 1e-10, abs_: float = 0.0) -> None:
        ok = math.isclose(a, b, rel_tol=rel, abs_tol=abs_)
        if not ok:
            _log_info("ASSERT isclose FAILED | a=%r b=%r rel=%r abs=%r", a, b, rel, abs_)
        self.assertTrue(ok, msg=f"Attendu ~{b!r} mais reçu {a!r}")

    def assertHasInconnue(self, rapport: dict, *, categorie: str, nom_contains: str) -> None:
        self.assertIn("inconnues", rapport)
        self.assertIn(categorie, rapport["inconnues"])
        items = rapport["inconnues"][categorie]
        ok = any(nom_contains in str(it.get("nom", "")) for it in items)
        if not ok:
            _log_info("INCONNUE NOT FOUND")
            _log_info("categorie=%s nom_contains=%s items=%r", categorie, nom_contains, items)
        self.assertTrue(ok, msg=f"Inconnue attendue en {categorie}: contenant {nom_contains!r}")

    # -------------------------------------------------------------------------
    # Nominal complet (sans dépendre de materiaux/air/eau) : overrides manuels
    # -------------------------------------------------------------------------

    def test_analyser_nominal_complet_overrides(self) -> None:
        # Entrées
        D = 0.100  # m
        S = 0.080  # m
        L = 0.120  # m
        p_serv = 2.0e6
        p_max = 5.0e6
        p_ext = 0.0
        FS = 2.0

        sigma_adm = 250.0e6  # Pa (avant FS)
        E = 210.0e9          # Pa
        nu = 0.30
        alpha = 12.0e-6      # 1/K
        k = 45.0             # W/m/K
        rho = 7800.0         # kg/m3

        h_i = 500.0
        h_o = 50.0
        dT = 50.0

        cyl = Cylindre(
            alesage_m=D,
            course_m=S,
            longueur_utile_m=L,
            pression_service_pa=p_serv,
            pression_max_pa=p_max,
            pression_externe_pa=p_ext,
            facteur_securite=FS,
            contrainte_admissible_pa=sigma_adm,
            module_young_pa=E,
            coefficient_poisson=nu,
            coefficient_dilatation_1_k=alpha,
            conductivite_w_m_k=k,
            densite_kg_m3=rho,
            h_interne_w_m2_k=h_i,
            h_externe_w_m2_k=h_o,
            delta_temperature_k=dT,
        )
        r = cyl.analyser(strict=False)

        _log_info("rapport keys=%s", list(r.keys()))

        # Géométrie attendue
        ri = 0.5 * D
        Ai = math.pi * (ri ** 2)
        V_swept = (math.pi * (D ** 2) / 4.0) * S
        V_int = Ai * L
        S_int_lat = math.pi * D * L

        self.assertIsClose(r["geometrie"]["rayon_interne_m"], ri, rel=0.0, abs_=0.0)
        self.assertIsClose(r["geometrie"]["aire_section_interne_m2"], Ai, rel=1e-14)
        self.assertIsClose(r["geometrie"]["cylindree_unitaire_m3"], V_swept, rel=1e-12)
        self.assertIsClose(r["geometrie"]["volume_interne_total_m3"], V_int, rel=1e-12)
        self.assertIsClose(r["geometrie"]["surface_interne_laterale_m2"], S_int_lat, rel=1e-12)

        # Efforts pression attendus
        F_serv = (p_serv - p_ext) * Ai
        F_max = (p_max - p_ext) * Ai
        self.assertIsClose(r["dimensionnement"]["force_pression_piston_service_N"], F_serv, rel=1e-12)
        self.assertIsClose(r["dimensionnement"]["force_pression_piston_max_N"], F_max, rel=1e-12)

        # Épaisseur attendue (même logique que le module)
        p_i = p_max
        p_o = p_ext
        delta_p = max(0.0, p_i - p_o)
        sigma_eff = sigma_adm / FS

        # paroi mince : t = (p*ri)/sigma_eff
        t_mince = (delta_p * ri) / sigma_eff

        # Lamé (formule interne du module)
        denom = (sigma_eff - p_i + 2.0 * p_o)
        self.assertTrue(denom > 0.0, "Choisir des valeurs de test où la solution Lamé existe.")
        ro2 = (ri * ri) * (sigma_eff + p_i) / denom
        t_lame = max(0.0, math.sqrt(ro2) - ri)

        t_ret = max(t_mince, t_lame)

        self.assertIsClose(r["dimensionnement"]["delta_p_dimensionnement_pa"], delta_p, rel=0.0, abs_=0.0)
        self.assertIsClose(r["dimensionnement"]["epaisseur_mince_m"], t_mince, rel=1e-12)
        self.assertIsClose(r["dimensionnement"]["epaisseur_lame_m"], t_lame, rel=1e-12)
        self.assertIsClose(r["dimensionnement"]["epaisseur_retenue_m"], t_ret, rel=1e-12)

        # Contraintes (mince)
        sigma_theta_mince = (delta_p * ri) / t_ret
        sigma_long_mince = (delta_p * ri) / (2.0 * t_ret)
        sigma_vm_mince = math.sqrt(
            sigma_theta_mince**2
            + sigma_long_mince**2
            - sigma_theta_mince * sigma_long_mince
        )
        self.assertIsClose(r["contraintes"]["sigma_cerclage_mince_pa"], sigma_theta_mince, rel=1e-12)
        self.assertIsClose(r["contraintes"]["sigma_longitudinale_mince_pa"], sigma_long_mince, rel=1e-12)
        self.assertIsClose(r["contraintes"]["sigma_von_mises_mince_pa"], sigma_vm_mince, rel=1e-12)

        # Contraintes Lamé au rayon interne
        ro = ri + t_ret
        ri2 = ri * ri
        ro2b = ro * ro
        denom2 = (ro2b - ri2)
        self.assertTrue(denom2 > 0.0)

        A = (p_i * ri2 - p_o * ro2b) / denom2
        B = (ri2 * ro2b * (p_i - p_o)) / denom2

        sigma_r_i = A - (B / ri2)
        sigma_theta_i = A + (B / ri2)
        sigma_z = A

        # check identité quand p_o=0 -> sigma_r(ri)=-p_i
        self.assertIsClose(sigma_r_i, -p_i, rel=1e-12)

        def von_mises_3d(s1: float, s2: float, s3: float) -> float:
            return math.sqrt(0.5 * ((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2))

        sigma_vm_lame = von_mises_3d(sigma_theta_i, sigma_r_i, sigma_z)

        self.assertIsClose(r["contraintes"]["sigma_radiale_lame_au_ri_pa"], sigma_r_i, rel=1e-12)
        self.assertIsClose(r["contraintes"]["sigma_cerclage_lame_au_ri_pa"], sigma_theta_i, rel=1e-12)
        self.assertIsClose(r["contraintes"]["sigma_axiale_lame_pa"], sigma_z, rel=1e-12)
        self.assertIsClose(r["contraintes"]["sigma_von_mises_lame_au_ri_pa"], sigma_vm_lame, rel=1e-12)

        # Vérif paroi mince
        ratio_t_sur_ri = t_ret / ri
        self.assertIsClose(r["geometrie"]["ratio_t_sur_ri"], ratio_t_sur_ri, rel=1e-12)
        self.assertEqual(r["verifications"]["hypothese_paroi_mince_ok"], ratio_t_sur_ri <= 0.10)

        # Déformations sous pression (si E, nu disponibles)
        eps_theta = (sigma_theta_mince - nu * sigma_long_mince) / E
        delta_ri_p = eps_theta * ri
        self.assertIsClose(r["deformations"]["epsilon_cerclage_sous_pression"], eps_theta, rel=1e-12)
        self.assertIsClose(r["deformations"]["augmentation_rayon_interne_pression_m"], delta_ri_p, rel=1e-12)
        self.assertIsClose(r["deformations"]["augmentation_diametre_interne_pression_m"], 2.0 * delta_ri_p, rel=1e-12)

        # Dilatation thermique (si alpha et dT)
        delta_D_th = alpha * D * dT
        self.assertIsClose(r["deformations"]["augmentation_diametre_interne_thermique_m"], delta_D_th, rel=1e-12)
        self.assertIsClose(r["deformations"]["augmentation_rayon_interne_thermique_m"], 0.5 * delta_D_th, rel=1e-12)

        # Thermique : Rcond + Rconv
        R_cond = math.log(ro / ri) / (2.0 * math.pi * k * L)
        A_i = 2.0 * math.pi * ri * L
        A_o = 2.0 * math.pi * ro * L
        R_ci = 1.0 / (h_i * A_i)
        R_co = 1.0 / (h_o * A_o)
        R_tot = R_ci + R_cond + R_co

        self.assertIsClose(r["thermique"]["R_conduction_K_W"], R_cond, rel=1e-12)
        self.assertIsClose(r["thermique"]["R_convection_interne_K_W"], R_ci, rel=1e-12)
        self.assertIsClose(r["thermique"]["R_convection_externe_K_W"], R_co, rel=1e-12)
        self.assertIsClose(r["thermique"]["R_totale_K_W"], R_tot, rel=1e-12)

        # Masse + inerties
        section_metal = math.pi * (ro * ro - ri * ri)
        volume_metal = section_metal * L
        masse = rho * volume_metal

        Do = 2.0 * ro
        Di = 2.0 * ri
        I = (math.pi / 64.0) * (Do ** 4 - Di ** 4)
        Jp = 2.0 * I

        self.assertIsClose(r["masse"]["section_metal_m2"], section_metal, rel=1e-12)
        self.assertIsClose(r["masse"]["volume_metal_m3"], volume_metal, rel=1e-12)
        self.assertIsClose(r["masse"]["masse_kg"], masse, rel=1e-12)
        self.assertIsClose(r["inerties"]["inertie_flexion_I_m4"], I, rel=1e-12)
        self.assertIsClose(r["inerties"]["inertie_polaire_J_m4"], Jp, rel=1e-12)

    # -------------------------------------------------------------------------
    # Bride (si fournie) : géométrie + volume brides + masse brides
    # -------------------------------------------------------------------------

    def test_brides_si_fournies(self) -> None:
        D = 0.100
        S = 0.080
        L = 0.120
        p_serv = 2.0e6
        p_max = 5.0e6
        p_ext = 0.0
        FS = 2.0
        sigma_adm = 250.0e6

        rho = 7800.0

        e_b = 0.010  # m
        w_b = 0.020  # m

        cyl = Cylindre(
            alesage_m=D,
            course_m=S,
            longueur_utile_m=L,
            pression_service_pa=p_serv,
            pression_max_pa=p_max,
            pression_externe_pa=p_ext,
            facteur_securite=FS,
            contrainte_admissible_pa=sigma_adm,
            densite_kg_m3=rho,
            epaisseur_bride_m=e_b,
            largeur_bride_m=w_b,
        )
        r = cyl.analyser(strict=False)

        t = r["dimensionnement"]["epaisseur_retenue_m"]
        self.assertIsInstance(t, float)
        self.assertTrue(t > 0.0)

        ri = 0.5 * D
        ro = ri + float(t)
        r_b = ro + w_b

        A_anneau = math.pi * (r_b * r_b - ro * ro)
        V_brides = 2.0 * A_anneau * e_b
        m_brides = rho * V_brides

        self.assertIsClose(r["geometrie"]["rayon_externe_avec_brides_m"], r_b, rel=1e-12)
        self.assertIsClose(r["geometrie"]["diametre_externe_avec_brides_m"], 2.0 * r_b, rel=1e-12)
        self.assertIsClose(r["geometrie"]["longueur_totale_avec_brides_m"], L + 2.0 * e_b, rel=1e-12)

        self.assertIsClose(r["masse"]["volume_brides_m3"], V_brides, rel=1e-12)
        self.assertIsClose(r["masse"]["masse_brides_kg"], m_brides, rel=1e-12)

    # -------------------------------------------------------------------------
    # Validation entrées : géométrie / pressions / FS
    # -------------------------------------------------------------------------

    def test_entrees_invalides_refuse(self) -> None:
        with self.assertRaises(ValueError):
            Cylindre(
                alesage_m=-0.1,
                course_m=0.1,
                longueur_utile_m=0.1,
                pression_service_pa=1.0,
                pression_max_pa=1.0,
            ).analyser()

        with self.assertRaises(ValueError):
            Cylindre(
                alesage_m=0.1,
                course_m=0.0,
                longueur_utile_m=0.1,
                pression_service_pa=1.0,
                pression_max_pa=1.0,
            ).analyser()

        with self.assertRaises(ValueError):
            Cylindre(
                alesage_m=0.1,
                course_m=0.1,
                longueur_utile_m=0.1,
                pression_service_pa=-1.0,
                pression_max_pa=1.0,
            ).analyser()

        with self.assertRaises(ValueError):
            Cylindre(
                alesage_m=0.1,
                course_m=0.1,
                longueur_utile_m=0.1,
                pression_service_pa=1.0,
                pression_max_pa=1.0,
                facteur_securite=0.0,
            ).analyser()

    # -------------------------------------------------------------------------
    # Inconnues : pas de sigma admissible (ni Re) => épaisseur impossible + strict
    # -------------------------------------------------------------------------

    def test_sans_contrainte_admissible_inconnue_et_strict_raise(self) -> None:
        cyl = Cylindre(
            alesage_m=0.1,
            course_m=0.08,
            longueur_utile_m=0.12,
            pression_service_pa=2e6,
            pression_max_pa=5e6,
            pression_externe_pa=0.0,
            # pas de contrainte_admissible_pa
            # pas de limite_elastique_pa
            # pas de materiau_cle
        )
        r = cyl.analyser(strict=False)
        _log_info("inconnues=%r", r["inconnues"])

        self.assertHasInconnue(r, categorie="impossibles", nom_contains="contrainte admissible")
        self.assertHasInconnue(r, categorie="impossibles", nom_contains="épaisseur cylindre")

        self.assertIsNone(r["dimensionnement"]["epaisseur_retenue_m"])

        with self.assertRaises(ValueError):
            cyl.analyser(strict=True)

    # -------------------------------------------------------------------------
    # Pression externe supérieure : module marque "impossible" (collapse non traité)
    # -------------------------------------------------------------------------

    def test_pression_externe_superieure_marque_impossible(self) -> None:
        cyl = Cylindre(
            alesage_m=0.1,
            course_m=0.08,
            longueur_utile_m=0.12,
            pression_service_pa=1e5,
            pression_max_pa=1e5,
            pression_externe_pa=2e5,  # p_o > p_i
            contrainte_admissible_pa=250e6,
            facteur_securite=2.0,
        )
        r = cyl.analyser(strict=False)
        self.assertHasInconnue(r, categorie="impossibles", nom_contains="pression externe")

    # -------------------------------------------------------------------------
    # Note modèle : p_max < p_serv -> note présente
    # -------------------------------------------------------------------------

    def test_note_pmax_inferieur_pserv(self) -> None:
        cyl = Cylindre(
            alesage_m=0.1,
            course_m=0.08,
            longueur_utile_m=0.12,
            pression_service_pa=5e6,
            pression_max_pa=2e6,  # p_max < p_serv
            pression_externe_pa=0.0,
            contrainte_admissible_pa=250e6,
            facteur_securite=2.0,
        )
        r = cyl.analyser(strict=False)
        notes = r.get("notes_modele", [])
        _log_info("notes=%r", notes)
        self.assertTrue(any("pression_max_pa < pression_service_pa" in str(x) for x in notes))

    # -------------------------------------------------------------------------
    # Convection : test robuste (selon dispo backend.ensemble.*)
    # - si dispo -> h calculé
    # - sinon -> inconnue partielle
    # -------------------------------------------------------------------------

    def test_convection_interne_calcule_ou_inconnue(self) -> None:
        D = 0.100
        cyl = Cylindre(
            alesage_m=D,
            course_m=0.08,
            longueur_utile_m=0.12,
            pression_service_pa=2e6,
            pression_max_pa=5e6,
            pression_externe_pa=0.0,
            contrainte_admissible_pa=250e6,
            facteur_securite=2.0,
            conductivite_w_m_k=45.0,  # pour activer la section thermique
            convection_interne=EntreeConvectionTube(
                fluide="air",
                T_K=288.15,
                p_Pa=101325.0,
                altitude_m=0.0,
                RH=0.0,
                co2_ppm=420.0,
                debit_massique_kg_s=0.05,
                diametre_m=0.020,
                modele="auto",
                condition_paroi="T_constante",
                chauffage_fluide=True,
            ),
        )
        r = cyl.analyser(strict=False)

        # Si air_state est dispo, on doit avoir "h_interne_calcule" dans thermique
        # Sinon, on doit avoir une inconnue partielle "h_interne"
        if cyl_mod.air_state is not None and cyl_mod.isa_dry_temperature_pressure is not None:
            self.assertIn("thermique", r)
            self.assertIn("h_interne_calcule", r["thermique"])
            hi = r["thermique"]["h_interne_calcule"]["h_W_m2_K"]
            _log_info("h_interne_calcule=%r", r["thermique"]["h_interne_calcule"])
            self.assertTrue(isinstance(hi, (int, float)) and math.isfinite(float(hi)) and float(hi) > 0.0)
        else:
            self.assertHasInconnue(r, categorie="partielles", nom_contains="h_interne")

    # -------------------------------------------------------------------------
    # calcul_h_depuis_entree_convection (direct) : test conditionnel
    # -------------------------------------------------------------------------

    def test_calcul_h_depuis_entree_convection_si_dispo(self) -> None:
        ent = EntreeConvectionTube(
            fluide="air",
            T_K=288.15,
            p_Pa=101325.0,
            altitude_m=0.0,
            RH=0.0,
            co2_ppm=420.0,
            debit_massique_kg_s=0.05,
            diametre_m=0.020,
            modele="auto",
            condition_paroi="T_constante",
            chauffage_fluide=True,
        )

        if cyl_mod.air_state is None or cyl_mod.isa_dry_temperature_pressure is None:
            _log_info("air_state / isa_dry_temperature_pressure indisponibles -> skip logique (test passe sans exiger)")
            return

        res = calcul_h_depuis_entree_convection(ent)
        _log_info("res_h=%r", res)
        self.assertIn("h_W_m2_K", res)
        self.assertTrue(float(res["h_W_m2_K"]) > 0.0)
        self.assertIn("Re", res)
        self.assertIn("Pr", res)
        self.assertIn("Nu", res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
