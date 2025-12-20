"""
Logging Setup - Configures application-wide logging with rotation.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(log_dir: Optional[str] = None,
                  log_level: int = logging.INFO) -> logging.Logger:
    """
    Setup application logging with file rotation and console handlers.
    
    Args:
        log_dir: Directory for log files (default: logs/ in package dir)
        log_level: Logging level (default: INFO)
        
    Returns:
        Root logger configured for the application
    """
    if log_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")

    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, "conversion_app.log")

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Rotating file handler: 10MB max, keep 5 backups
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger("office_converter")
    logger.setLevel(log_level)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("=" * 50)
    logger.info("Office Converter started")
    logger.info(f"Log file: {log_path} (rotating)")

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"office_converter.{name}")
