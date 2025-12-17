"""
Word Converter - Converts Word documents to PDF using COM automation.
Uses COM Pool for connection reuse and memory optimization.
"""

import os
import time
import logging
import shutil
import gc
from typing import Optional, Callable

import pythoncom

from .base import BaseConverter
from ..utils.com_pool import get_pool

logger = logging.getLogger(__name__)

# Word constants
wdExportFormatPDF = 17
wdExportOptimizeForPrint = 0
wdExportOptimizeForOnScreen = 1


class WordConverter(BaseConverter):
    """Converter for Word documents (.docx, .doc, .docm, .rtf)."""
    
    SUPPORTED_EXTENSIONS = [".docx", ".doc", ".docm", ".rtf"]
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        super().__init__(log_callback, progress_callback)
        self._word = None
        self._use_pool = False  # Disabled pool due to COM corruption issues
    
    def initialize(self) -> bool:
        """Get Word COM from pool."""
        try:
            pythoncom.CoInitialize()
            if self._use_pool:
                self._word = get_pool().get_word()
            else:
                import win32com.client
                self._word = win32com.client.Dispatch("Word.Application")
                self._configure_standalone()
            
            if self._word:
                logger.info("Word ready (pooled)" if self._use_pool else "Word ready (standalone)")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Word: {e}")
            return False
    
    def _configure_standalone(self):
        """Configure standalone Word instance."""
        self._word.Visible = False
        self._word.DisplayAlerts = 0
        try:
            self._word.Options.CheckSpellingAsYouType = False
            self._word.Options.CheckGrammarAsYouType = False
            self._word.AutomationSecurity = 3
        except:
            pass
    
    def cleanup(self):
        """Release Word resources."""
        if not self._use_pool and self._word:
            try:
                self._word.Quit()
            except:
                pass
            self._word = None
        # Note: Don't set to None when using pool
        gc.collect()
        logger.info("Word cleanup done")
    
    def convert(self, input_path: str, output_path: str, 
                quality: int = 0) -> bool:
        """
        Convert Word document to PDF.
        """
        if not self._word:
            if not self.initialize():
                return False
        
        doc = None
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        safe_id = str(int(time.time() * 1000))
        
        # Preserve original extension for proper handling
        ext = os.path.splitext(input_path)[1].lower()
        com_input_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}{ext}"))
        com_pdf_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}.pdf"))
        
        try:
            shutil.copyfile(input_path, com_input_path)
            
            doc = self._word.Documents.Open(
                com_input_path,
                ConfirmConversions=False,
                ReadOnly=True,
                AddToRecentFiles=False,
                Visible=False,
                NoEncodingDialog=True
            )
            
            optimize = wdExportOptimizeForPrint if quality == 0 else wdExportOptimizeForOnScreen
            doc.ExportAsFixedFormat(
                OutputFileName=com_pdf_path,
                ExportFormat=wdExportFormatPDF,
                OptimizeFor=optimize,
                CreateBookmarks=1,
                DocStructureTags=True,
                BitmapMissingFonts=True
            )
            
            doc.Close(False)
            doc = None
            
            # Move to final destination with retry for locked files
            if os.path.exists(com_pdf_path):
                # Try to remove existing output with retries
                for attempt in range(3):
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        break
                    except PermissionError:
                        time.sleep(0.3)  # Wait and retry
                
                shutil.move(com_pdf_path, output_path)
            
            try:
                os.remove(com_input_path)
            except:
                pass
            
            logger.info(f"Word converted: {os.path.basename(input_path)}")
            return True
            
        except Exception as e:
            logger.error(f"Word conversion failed: {e}")
            if doc:
                try:
                    doc.Close(False)
                except:
                    pass
            return False
        finally:
            gc.collect()

