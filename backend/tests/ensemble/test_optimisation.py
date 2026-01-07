import logging
import os
import pytest

# Configuration du logging
LOG_FILE = os.path.join(os.path.dirname(__file__), "test_optimisation.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
    encoding="utf-8"
)
logger = logging.getLogger("test_optimisation")

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