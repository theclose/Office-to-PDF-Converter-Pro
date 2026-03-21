"""
Localization Module - Multi-language support.
"""

from typing import Dict

import os
import sys
import json
import logging

logger = logging.getLogger(__name__)

# Cache for the currently loaded language dictionary
_loaded_translations: Dict[str, str] = {}
_fallback_translations: Dict[str, str] = {}

# Keep only the names for the settings dropdown
AVAILABLE_LANGUAGES: Dict[str, str] = {
    "vi": "Tiếng Việt",
    "en": "English",
    "zh": "简体中文",
    "ja": "日本語",
    "ko": "한국어"
}

def _get_locales_dir() -> str:
    """Get the path to the locales directory, supporting PyInstaller bundles."""
    if getattr(sys, 'frozen', False):
        # Running in a PyInstaller bundle
        base_path = sys._MEIPASS
    else:
        # Running in normal Python environment
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, 'locales')

def _load_language(lang_code: str) -> Dict[str, str]:
    """Load language dictionary from JSON."""
    locales_dir = _get_locales_dir()
    lang_file = os.path.join(locales_dir, f"{lang_code}.json")
    
    try:
        if os.path.exists(lang_file):
            with open(lang_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        else:
            logger.warning(f"Language file not found: {lang_file}")
            return {}
    except Exception as e:
        logger.error(f"Error loading language {lang_code}: {e}")
        return {}

# Current language (default to Vietnamese)
_current_lang = "vi"


def set_language(lang_code: str):
    """Set the current language and load its translations."""
    global _current_lang, _loaded_translations, _fallback_translations
    if lang_code in AVAILABLE_LANGUAGES:
        _current_lang = lang_code
        _loaded_translations = _load_language(lang_code)
        
        # Load English as fallback if not already English
        if lang_code != "en" and not _fallback_translations:
            _fallback_translations = _load_language("en")


def get_current_language() -> str:
    """Get current language code."""
    return _current_lang


def get_text(key: str, lang: str = None) -> str:
    """
    Get translated text for a key.
    
    Args:
        key: Translation key
        lang: Language code (optional, ignored now, uses current)
        
    Returns:
        Translated string or key if not found
    """
    # Ensure translations are loaded on first use
    global _loaded_translations
    if not _loaded_translations:
        set_language(_current_lang)

    # Return translated text
    if key in _loaded_translations:
        return _loaded_translations[key]
        
    # Fallback to English
    if key in _fallback_translations:
        return _fallback_translations[key]
        
    return key


def get_language_names() -> Dict[str, str]:
    """Get dictionary of language code -> display name."""
    return AVAILABLE_LANGUAGES
