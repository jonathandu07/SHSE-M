import logging
import os
import pytest

# Configuration du logging
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "logs"))
LOG_FILE = os.path.join(LOG_DIR, "test_optimisation.log")
logger = logging.getLogger("test_optimisation")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

def log_test_result(test_name, status, details=""):
    logger.info(f"RESULT - {test_name}: {status} {details}")

def test_import_optimisation():
    logger.info("Starting test_import_optimisation")
    try:
        import backend.ensemble.optimisation as opt
        assert opt is not None
        log_test_result("test_import_optimisation", "SUCCESS", "Module correctly imported.")
    except Exception as e:
        log_test_result("test_import_optimisation", "FAILED", str(e))
        raise


def test_optimisation_systeme_accepts_named_args_and_backend_reports():
    logger.info("Starting test_optimisation_systeme_accepts_named_args_and_backend_reports")
    try:
        from backend.ensemble.optimisation import OptimisationSysteme

        rapport_backend = {
            "synthese": {
                "moteur_thermique": {
                    "alesage_m": 0.13,
                    "course_m": 0.15,
                    "nombre_cylindres": 4,
                    "rpm_nominal": 1500.0,
                    "pme_pa": 1.5e6,
                    "pression_max_pa": 1.8e7,
                    "architecture": "L4",
                    "puissance_requise_W": 55000.0,
                },
                "vehicule": {
                    "tension_bus_dc_v": 400.0,
                    "puissance_bus_dc_design_w": 30000.0,
                },
            },
            "cao": {
                "solidworks_ready": True,
                "moteur_thermique": {
                    "alesage_mm": 130.0,
                    "course_mm": 150.0,
                },
            },
        }
        rapports_pieces = {
            "cylindre": {
                "entrees": {
                    "alesage_m": 0.13,
                    "course_m": 0.15,
                    "longueur_utile_m": 0.225,
                    "pression_service_pa": 1.0e7,
                    "pression_max_pa": 1.8e7,
                },
                "dimensionnement": {
                    "epaisseur_retenue_m": 0.008,
                },
            },
            "piston": {
                "entrees": {
                    "alesage_nominal_m": 0.13,
                },
                "geometrie": {
                    "diametre_exterieur_m": 0.1295,
                },
                "etancheite": {
                    "jeu_radial_froid_m": 0.00025,
                },
            },
        }

        opt = OptimisationSysteme(
            systeme_complet=rapport_backend,
            cylindre={"rapport": rapports_pieces["cylindre"]},
            piston={"rapport": rapports_pieces["piston"]},
            rapport_backend=rapport_backend,
            rapports_pieces=rapports_pieces,
        )

        analyse = opt.analyser()

        assert analyse["rapports_sources"]["systeme_complet"] is True
        assert analyse["rapports_sources"]["cylindre"] is True
        assert analyse["extractions"]["systeme_complet"]["alesage_m"] == pytest.approx(0.13)
        assert analyse["extractions"]["piston"]["diametre_exterieur_m"] == pytest.approx(0.1295)
        assert "synthese_optimisation" in analyse
        synthese = analyse["synthese_optimisation"]
        assert "score_efficience_energetique_100" in synthese
        assert "score_fiabilite_mecanique_100" in synthese
        assert "score_duree_vie_batterie_100" in synthese
        assert "score_conditions_utilisation_100" in synthese
        assert 0.0 <= synthese["score_global_100"] <= 100.0
        log_test_result(
            "test_optimisation_systeme_accepts_named_args_and_backend_reports",
            "SUCCESS",
            "Named arguments and backend report fallback work correctly.",
        )
    except Exception as e:
        log_test_result(
            "test_optimisation_systeme_accepts_named_args_and_backend_reports",
            "FAILED",
            str(e),
        )
        raise

if __name__ == "__main__":
    pytest.main([__file__])
