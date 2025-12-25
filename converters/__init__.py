# Converters Module - Lazy Loading for Fast Startup
"""
Lazy-loads converter classes on first access to improve app startup time.
Heavy COM-dependent modules are only loaded when actually needed.
"""

# Always available (lightweight)
from .base import BaseConverter, get_converter_for_file, get_best_converter

# Lazy loading for heavy converters
_excel_converter = None
_word_converter = None
_ppt_converter = None
_libreoffice_converter = None
_has_libreoffice = None
_is_libreoffice_available = None


def __getattr__(name):
    """Lazy load heavy converter classes on first access."""
    global _excel_converter, _word_converter, _ppt_converter
    global _libreoffice_converter, _has_libreoffice, _is_libreoffice_available
    
    if name == "ExcelConverter":
        if _excel_converter is None:
            from .excel import ExcelConverter as _ec
            globals()["_excel_converter"] = _ec
            globals()["ExcelConverter"] = _ec
        return globals().get("ExcelConverter") or _excel_converter
    
    elif name == "WordConverter":
        if _word_converter is None:
            from .word import WordConverter as _wc
            globals()["_word_converter"] = _wc
            globals()["WordConverter"] = _wc
        return globals().get("WordConverter") or _word_converter
    
    elif name == "PPTConverter":
        if _ppt_converter is None:
            from .ppt import PPTConverter as _pc
            globals()["_ppt_converter"] = _pc
            globals()["PPTConverter"] = _pc
        return globals().get("PPTConverter") or _ppt_converter
    
    elif name == "LibreOfficeConverter":
        if _libreoffice_converter is None:
            from .libreoffice import LibreOfficeConverter as _loc
            globals()["_libreoffice_converter"] = _loc
            globals()["LibreOfficeConverter"] = _loc
        return globals().get("LibreOfficeConverter") or _libreoffice_converter
    
    elif name == "HAS_LIBREOFFICE":
        if _has_libreoffice is None:
            from .libreoffice import HAS_LIBREOFFICE as _hlo
            globals()["_has_libreoffice"] = _hlo
            globals()["HAS_LIBREOFFICE"] = _hlo
        return globals().get("HAS_LIBREOFFICE", False)
    
    elif name == "is_libreoffice_available":
        if _is_libreoffice_available is None:
            from .libreoffice import is_libreoffice_available as _ila
            globals()["_is_libreoffice_available"] = _ila
            globals()["is_libreoffice_available"] = _ila
        return globals().get("is_libreoffice_available") or _is_libreoffice_available
    
    raise AttributeError(f"module 'converters' has no attribute '{name}'")


__all__ = [
    "BaseConverter",
    "ExcelConverter",
    "WordConverter",
    "PPTConverter",
    "LibreOfficeConverter",
    "get_converter_for_file",
    "get_best_converter",
    "is_libreoffice_available",
    "HAS_LIBREOFFICE",
]

