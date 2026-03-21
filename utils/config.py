"""
Configuration Management - Centralized settings handling.
"""

import os
import json
import copy
import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Default config values
DEFAULT_CONFIG = {
    "language": "vi",
    "theme": "light",
    "pdf_quality": 0,
    "auto_compress": False,
    "last_folder": "",
    "output_folder": "",
    "metadata": {
        "author": "",
        "title": "",
        "password_enabled": False
    },
    "scan_mode": False
}


class Config:
    """Centralized configuration manager."""

    _instance = None
    _config_path = None
    _data: Dict[str, Any] = {}
    _initialized = False
    _save_lock = threading.Lock()  # M3: Prevent concurrent config.json corruption

    def __new__(cls, config_path: Optional[str] = None):
        """Singleton pattern - only one config instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        if config_path:
            self._config_path = config_path
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self._config_path = os.path.join(base_dir, "config.json")

        # Use deepcopy to prevent nested dict mutation
        self._data = copy.deepcopy(DEFAULT_CONFIG)
        self.load()
        self._initialized = True

    def load(self) -> bool:
        """Load config from file."""
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._data = {**copy.deepcopy(DEFAULT_CONFIG), **loaded}
                    logger.info(f"Config loaded from {self._config_path}")
                    return True
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
        return False

    def save(self) -> bool:
        """Save config to file (thread-safe)."""
        try:
            with self._save_lock:
                with open(self._config_path, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
            logger.info(f"Config saved to {self._config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True):
        """Set a config value."""
        self._data[key] = value
        if auto_save:
            self.save()

    @property
    def language(self) -> str:
        return self.get("language", "vi")

    @language.setter
    def language(self, value: str):
        self.set("language", value)

    @property
    def theme(self) -> str:
        return self.get("theme", "light")

    @theme.setter
    def theme(self, value: str):
        self.set("theme", value)

    @property
    def pdf_quality(self) -> int:
        return self.get("pdf_quality", 0)

    @pdf_quality.setter
    def pdf_quality(self, value: int):
        self.set("pdf_quality", value)
