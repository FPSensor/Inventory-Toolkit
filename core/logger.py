"""Inventory Toolkit logging configuration."""

import logging
import os


def setup_logger(debug_level=1):
    levels = {
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
    }
    level = levels.get(debug_level, logging.ERROR)

    logger = logging.getLogger("InventoryToolkit")
    logger.setLevel(level)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Persistent session log used for post-run diagnostics.
        os.makedirs("logs", exist_ok=True)
        file_handler = logging.FileHandler("logs/session.log", mode="w", encoding="utf-8")
        file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    for handler in logger.handlers:
        handler.setLevel(level)

    return logger


log = logging.getLogger("InventoryToolkit")
