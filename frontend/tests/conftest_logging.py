import logging
import os
from datetime import datetime

def setup_test_logging(test_name: str):
    """
    Configure le logging pour redirecter les sorties vers frontend/logs/
    """
    log_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs"))
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    log_filename = f"{test_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(log_dir, log_filename)
    
    logger = logging.getLogger(test_name)
    logger.setLevel(logging.DEBUG)
    
    # Éviter d'ajouter plusieurs handlers si le logger existe déjà
    if not logger.handlers:
        fh = logging.FileHandler(log_path, encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
    return logger
