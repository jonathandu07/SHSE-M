import logging
import math
from typing import Dict, Any, List, Optional
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
    handlers=[
        logging.FileHandler("design_log.txt", mode='w'),
        logging.StreamHandler(sys.stdout)
    ]
)

class Agent:
    """Base class for all sizing agents."""
    
    def __init__(self, config: Dict[str, Any], agent_name: str):
        self.config = config
        self.name = agent_name
        self.logger = logging.getLogger(agent_name)
        self.results = {}
        self.warnings = []

    def log(self, message: str):
        self.logger.info(message)
    
    def warn(self, message: str):
        self.logger.warning(message)
        self.warnings.append(message)
        
    def check(self, condition: bool, error_msg: str, warn_only: bool = False):
        """
        Verifies a condition.
        If warn_only is False and condition is False, raises RuntimeError.
        If warn_only is True and condition is False, logs warning.
        """
        if not condition:
            if warn_only:
                self.warn(f"CHECK FAILED: {error_msg}")
            else:
                self.logger.error(f"CRITICAL CHECK FAILED: {error_msg}")
                raise RuntimeError(f"[{self.name}] {error_msg}")
        else:
            self.logger.debug(f"Check passed: {error_msg}")

    def get_material(self, key: str) -> Dict[str, float]:
        """Helper to retrieve material properties from config."""
        # Simple lookup in config['materials']
        # Mappings can be hardcoded here or in config
        mat_map = {
            "piston": "aluminum_piston",
            "rod": "steel_alloy",
            "crank": "steel_alloy",
            "block": "aluminum_block",
            "bolt": "steel_alloy"
        }
        mat_id = mat_map.get(key, "steel_alloy")
        return self.config['materials'][mat_id]

    def run(self) -> Dict[str, Any]:
        raise NotImplementedError("Agent must implement run()")
