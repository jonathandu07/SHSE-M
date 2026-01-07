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

if __name__ == "__main__":
    pytest.main([__file__])