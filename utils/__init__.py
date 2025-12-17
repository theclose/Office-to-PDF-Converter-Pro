# Utils Module
from .config import Config
from .localization import get_text, LANGUAGES, set_language, get_current_language
from .pdf_tools import merge_pdfs, split_pdf, rasterize_pdf, post_process_pdf, parse_page_range, HAS_PYMUPDF
from .logging_setup import setup_logging, get_logger
from .com_pool import COMPool, get_pool, release_pool
from .history import ConversionHistory, get_history

__all__ = [
    "Config", 
    "get_text", "LANGUAGES", "set_language", "get_current_language",
    "merge_pdfs", "split_pdf", "rasterize_pdf", "post_process_pdf", "parse_page_range", "HAS_PYMUPDF",
    "setup_logging", "get_logger",
    "COMPool", "get_pool", "release_pool",
    "ConversionHistory", "get_history"
]
