import logging
import os

def setup_logger(nivel_debug=1):
    niveles = {
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO
    }
    level = niveles.get(nivel_debug, logging.ERROR)
    
    logger = logging.getLogger("InventoryToolkit")
    logger.setLevel(level)
    
    if not logger.handlers:
        # Console Handler
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File Handler (Persistente para Magoya)
        os.makedirs('logs', exist_ok=True)
        fh = logging.FileHandler('logs/session.log', mode='w', encoding='utf-8')
        fh_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fh.setFormatter(fh_formatter)
        logger.addHandler(fh)
        
    for handler in logger.handlers:
        handler.setLevel(level)
    
    return logger

log = logging.getLogger("InventoryToolkit")
