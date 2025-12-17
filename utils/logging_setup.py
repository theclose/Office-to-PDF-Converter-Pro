"""
Logging Setup - Configures application-wide logging to file and console.
"""

import os
import logging
from datetime import datetime
from typing import Optional


def setup_logging(log_dir: Optional[str] = None, 
                  log_level: int = logging.INFO) -> logging.Logger:
    """
    Setup application logging with file and console handlers.
    
    Args:
        log_dir: Directory for log files (default: logs/ in package dir)
        log_level: Logging level (default: INFO)
        
    Returns:
        Root logger configured for the application
    """
    # Determine log directory
    if log_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
    
    # Create logs directory if not exists
    os.makedirs(log_dir, exist_ok=True)
    
    # Log file with date
    log_filename = f"conversion_{datetime.now().strftime('%Y%m%d')}.log"
    log_path = os.path.join(log_dir, log_filename)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler (append mode)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
    console_handler.setFormatter(formatter)
    
    # Get root logger for our package
    logger = logging.getLogger("office_converter")
    logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info("="*50)
    logger.info("Office Converter started")
    logger.info(f"Log file: {log_path}")
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"office_converter.{name}")
