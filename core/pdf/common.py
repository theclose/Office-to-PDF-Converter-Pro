"""
Common utilities and lazy loaders for PDF tools.
"""

import logging

logger = logging.getLogger("pdf_tools")

# fitz is lazy-loaded to avoid massive memory usage (~30MB) at startup
_fitz = None
HAS_PYMUPDF: bool = False

def get_fitz():
    """Lazy import fitz (PyMuPDF) on first use."""
    global _fitz, HAS_PYMUPDF
    if _fitz is None:
        try:
            import fitz
            _fitz = fitz
            HAS_PYMUPDF = True
            logger.info("PyMuPDF loaded successfully")
        except ImportError:
            _fitz = False
            HAS_PYMUPDF = False
            logger.warning("PyMuPDF (fitz) not found!")
    return _fitz if _fitz is not False else None

# Check for PIL for image processing
try:
    from PIL import Image, ImageFilter, ImageEnhance, ImageChops
    import random
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
