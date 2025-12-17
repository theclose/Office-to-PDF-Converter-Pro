"""
PowerPoint Converter - Converts presentations to PDF using COM automation.
"""

import os
import logging
import shutil
import gc
import uuid
from typing import Optional, Callable

import pythoncom

from .base import BaseConverter
from ..utils.com_pool import get_pool

logger = logging.getLogger(__name__)

# PowerPoint constants
ppSaveAsPDF = 32


class PPTConverter(BaseConverter):
    """Converter for PowerPoint presentations (.pptx, .ppt, .pptm)."""
    
    SUPPORTED_EXTENSIONS = [".pptx", ".ppt", ".pptm", ".ppsx", ".pps"]
    
    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        super().__init__(log_callback, progress_callback)
        self._ppt = None
        self._use_pool = False
    
    def initialize(self) -> bool:
        """Get PowerPoint COM from pool."""
        try:
            pythoncom.CoInitialize()
            if self._use_pool:
                self._ppt = get_pool().get_ppt()
            else:
                import win32com.client
                self._ppt = win32com.client.Dispatch("PowerPoint.Application")
                self._configure_standalone()
            
            if self._ppt:
                logger.info("PowerPoint ready (pooled)" if self._use_pool else "PPT ready (standalone)")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize PowerPoint: {e}")
            return False
    
    def _configure_standalone(self):
        """Configure standalone PowerPoint instance."""
        try:
            self._ppt.DisplayAlerts = 0
        except Exception as e:
            logger.debug(f"PPT configure warning: {e}")
    
    def cleanup(self):
        """Release PowerPoint resources."""
        if not self._use_pool and self._ppt:
            try:
                self._ppt.Quit()
            except Exception as e:
                logger.debug(f"PPT quit error: {e}")
            self._ppt = None
        
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        
        gc.collect()
        logger.info("PowerPoint cleanup done")
    
    def convert(self, input_path: str, output_path: str, 
                quality: int = 0) -> bool:
        """Convert PowerPoint presentation to PDF."""
        if not self._ppt:
            if not self.initialize():
                return False
        
        presentation = None
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        safe_id = uuid.uuid4().hex
        
        ext = os.path.splitext(input_path)[1].lower()
        com_input_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}{ext}"))
        com_pdf_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}.pdf"))
        
        try:
            shutil.copyfile(input_path, com_input_path)
            
            presentation = self._ppt.Presentations.Open(
                com_input_path,
                ReadOnly=True,
                Untitled=False,
                WithWindow=False
            )
            
            presentation.SaveAs(com_pdf_path, ppSaveAsPDF)
            
            presentation.Close()
            presentation = None
            
            if os.path.exists(com_pdf_path):
                if os.path.exists(output_path):
                    os.remove(output_path)
                shutil.move(com_pdf_path, output_path)
            
            try:
                if os.path.exists(com_input_path):
                    os.remove(com_input_path)
            except Exception:
                pass
            
            logger.info(f"PowerPoint converted: {os.path.basename(input_path)}")
            return True
            
        except Exception as e:
            logger.error(f"PowerPoint conversion failed: {e}")
            if presentation:
                try:
                    presentation.Close()
                except Exception:
                    pass
            return False
        finally:
            if os.path.exists(com_pdf_path):
                try:
                    os.remove(com_pdf_path)
                except Exception:
                    pass
            gc.collect()
