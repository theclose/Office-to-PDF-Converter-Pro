"""
Base Converter - Abstract class for all Office converters.
All specific converters (Excel, Word, PPT) inherit from this.
"""

import os
import logging
import threading
from abc import ABC, abstractmethod
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)

# Thread-local storage for COM initialization tracking
_com_init_count = threading.local()


def ensure_com_initialized():
    """Ensure COM is initialized for the current thread. Returns True if newly initialized."""
    import pythoncom
    
    if not hasattr(_com_init_count, 'count'):
        _com_init_count.count = 0
    
    if _com_init_count.count == 0:
        pythoncom.CoInitialize()
        _com_init_count.count = 1
        logger.debug(f"COM initialized for thread {threading.current_thread().name}")
        return True
    else:
        _com_init_count.count += 1
        return False


def release_com():
    """Release COM for the current thread if this was the last user."""
    import pythoncom
    
    if not hasattr(_com_init_count, 'count') or _com_init_count.count <= 0:
        return
    
    _com_init_count.count -= 1
    
    if _com_init_count.count == 0:
        try:
            pythoncom.CoUninitialize()
            logger.debug(f"COM released for thread {threading.current_thread().name}")
        except Exception as e:
            logger.debug(f"COM release warning: {e}")


class BaseConverter(ABC):
    """Abstract base class for Office document converters."""

    # Subclasses must define supported extensions
    SUPPORTED_EXTENSIONS: List[str] = []

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        """
        Initialize converter.
        
        Args:
            log_callback: Function to call for logging messages to UI
            progress_callback: Function to call with progress (0.0 to 1.0)
        """
        self.log_callback = log_callback or (lambda msg: None)
        self.progress_callback = progress_callback or (lambda pct: None)
        self._app = None  # COM application instance
        self._com_owned = False  # Track if this instance initialized COM

    def log(self, message: str):
        """Log a message to both file and UI callback."""
        logger.info(message)
        self.log_callback(message)

    def update_progress(self, percent: float):
        """Update progress (0.0 to 1.0)."""
        self.progress_callback(min(1.0, max(0.0, percent)))

    @classmethod
    def supports_file(cls, file_path: str) -> bool:
        """Check if this converter supports the given file."""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in cls.SUPPORTED_EXTENSIONS

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the COM application.
        Returns True if successful.
        """
        pass

    @abstractmethod
    def convert(self, input_path: str, output_path: str, **options) -> bool:
        """
        Convert a single file to PDF.
        
        Args:
            input_path: Path to input Office document
            output_path: Path to output PDF file
            **options: Converter-specific options
            
        Returns:
            True if conversion successful
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Release COM resources."""
        pass

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
        return False


def get_converter_for_file(file_path: str) -> Optional[type]:
    """
    Factory function to get appropriate converter class for a file.
    Returns MS Office converter classes (requires MS Office to be installed).
    
    Args:
        file_path: Path to the file
        
    Returns:
        Converter class (not instance) or None if unsupported
    """
    from .excel import ExcelConverter
    from .word import WordConverter
    from .ppt import PPTConverter

    converters = [ExcelConverter, WordConverter, PPTConverter]

    for converter_class in converters:
        if converter_class.supports_file(file_path):
            return converter_class

    return None


def get_best_converter(file_path: str, prefer_libreoffice: bool = False) -> Optional[type]:
    """
    Get the best available converter for a file.
    Tries MS Office first, falls back to LibreOffice if MS Office fails.
    
    Args:
        file_path: Path to the file
        prefer_libreoffice: If True, prefer LibreOffice over MS Office
        
    Returns:
        Converter class (not instance) or None if no converter available
    """
    from .libreoffice import LibreOfficeConverter, HAS_LIBREOFFICE

    # Get MS Office converter
    ms_converter = get_converter_for_file(file_path)

    # Check if file is supported by LibreOffice
    lo_available = HAS_LIBREOFFICE and LibreOfficeConverter.supports_file(file_path)

    if prefer_libreoffice:
        # Prefer LibreOffice
        if lo_available:
            return LibreOfficeConverter
        elif ms_converter:
            return ms_converter
    else:
        # Prefer MS Office (default)
        if ms_converter:
            # Try to verify MS Office is available
            try:
                import win32com.client
                # MS Office converter found and COM available
                return ms_converter
            except ImportError:
                # No COM support, fall back to LibreOffice
                if lo_available:
                    logger.info("MS Office COM not available, using LibreOffice")
                    return LibreOfficeConverter
                return ms_converter  # Return anyway, let it fail gracefully
        elif lo_available:
            return LibreOfficeConverter

    return None

