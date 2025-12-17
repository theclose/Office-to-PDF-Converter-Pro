"""
Base Converter - Abstract class for all Office converters.
All specific converters (Excel, Word, PPT) inherit from this.
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)


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
