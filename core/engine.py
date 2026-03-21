"""
Core Conversion Engine
Handles file conversion orchestration with progress callbacks.
"""

import os
import time
import threading
from pathlib import Path
from typing import List, Optional, Set, Dict, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from office_converter.utils.logging_setup import get_logger
from office_converter.utils.pdf_tools import (
    post_process_pdf, rasterize_pdf, parse_page_range, extract_pdf_pages
)
from office_converter.core.pdf.common import get_fitz
from office_converter.converters import get_converter_for_file
from office_converter.utils.recent_files import RecentFilesDB
from office_converter.utils.watchdog import start_watchdog, stop_watchdog, record_watchdog_conversion

logger = get_logger("ConversionEngine")

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

class FileType(Enum):
    EXCEL = auto()
    WORD = auto()
    POWERPOINT = auto()
    UNKNOWN = auto()

FILE_EXTENSIONS: Dict[FileType, Set[str]] = {
    FileType.EXCEL: {".xlsx", ".xls", ".xlsm", ".xlsb"},
    FileType.WORD: {".docx", ".doc", ".docm", ".rtf"},
    FileType.POWERPOINT: {".pptx", ".ppt", ".pptm", ".ppsx", ".pps"},
}

ALL_EXTENSIONS = set().union(*FILE_EXTENSIONS.values())

FILE_TYPE_COLORS = {
    FileType.EXCEL: "#217346",      # Excel green
    FileType.WORD: "#2B579A",       # Word blue
    FileType.POWERPOINT: "#D24726", # PPT orange
}

FILE_TYPE_ICONS = {
    FileType.EXCEL: "📗",
    FileType.WORD: "📘",
    FileType.POWERPOINT: "📙",
}


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class ConversionFile:
    """Represents a file to be converted."""
    path: str
    file_type: FileType = field(init=False)
    status: str = "pending"  # pending, converting, completed, failed
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0

    def __post_init__(self):
        self.file_type = self._detect_type()

    def _detect_type(self) -> FileType:
        ext = Path(self.path).suffix.lower()
        for ftype, extensions in FILE_EXTENSIONS.items():
            if ext in extensions:
                return ftype
        return FileType.UNKNOWN

    @property
    def filename(self) -> str:
        return Path(self.path).name

    @property
    def icon(self) -> str:
        return FILE_TYPE_ICONS.get(self.file_type, "📄")


@dataclass
class ConversionOptions:
    """Conversion settings.
    
    Quality presets:
        0 = Tối đa (Maximum) — COM high quality, no compression
        1 = Cao (High) — COM high quality, light compression
        2 = Cân bằng (Balanced) — COM high quality, medium compression  
        3 = Nhỏ gọn (Compact) — COM low quality, heavy compression
        4 = Custom — user-specified DPI
    """
    quality: int = 0  # 0=max, 1=high, 2=balanced, 3=compact, 4=custom
    quality_dpi: int = 300  # only used if quality=4
    auto_compress: bool = False  # auto-compress PDF after conversion
    scan_mode: bool = False
    password: Optional[str] = None
    page_range: Optional[str] = None
    sheet_indices: Optional[List[int]] = None
    author: Optional[str] = None
    title: Optional[str] = None

    @property
    def com_quality(self) -> int:
        """Map quality preset to COM Quality param (0=high, 1=low)."""
        if self.quality >= 3:  # Compact or Custom with low DPI
            return 1  # Screen quality (96dpi)
        return 0  # Print quality (300dpi)

    @property
    def compress_level(self) -> Optional[str]:
        """Map quality preset to compression level."""
        return {
            0: None,       # Tối đa: no compression
            1: "high",     # Cao: light compression
            2: "medium",   # Cân bằng: balanced compression
            3: "low",      # Nhỏ gọn: heavy compression
            4: None,       # Custom: no auto-compress
        }.get(self.quality)

# ============================================================================
# CONVERSION ENGINE
# ============================================================================

class ConversionEngine:
    """Handles file conversion with progress callbacks."""

    def __init__(self, on_progress: Optional[Callable] = None,
                 on_file_complete: Optional[Callable] = None,
                 on_error: Optional[Callable] = None):
        self.on_progress = on_progress
        self.on_file_complete = on_file_complete
        self.on_error = on_error
        self._stop_requested = False
        self._stop_event = threading.Event()
        self._current_converter = None  # Track current converter for force stop
        self._current_output_path = None  # Track current output file for cleanup
        self._incomplete_files: Set[str] = set()  # T4: set for O(1) discard
        self._db = RecentFilesDB()

    def stop(self, force: bool = False):
        """Request conversion stop.
        
        Args:
            force: If True, attempt to forcefully terminate Office processes.
        """
        self._stop_requested = True
        self._stop_event.set()
        
        if force:
            self._force_stop()

    def _force_stop(self):
        """Force stop by killing Office processes and cleaning up files.
        F1: Don't call converter.cleanup() here — it was created on the worker
        thread (STA), calling COM methods from main thread causes deadlock."""
        try:
            # Just null the reference — don't call cleanup() cross-thread
            self._current_converter = None
            
            # Kill hanging Office processes first
            self._kill_office_processes()
            
            # Clean up incomplete/partial output files
            self._cleanup_incomplete_files()
            
        except Exception as e:
            logger.error(f"Force stop error: {e}")

    def _cleanup_incomplete_files(self):
        """Clean up incomplete output files and temp files."""
        try:
            import glob
            
            # Clean up current output file if it exists and is incomplete
            if self._current_output_path and os.path.exists(self._current_output_path):
                try:
                    os.remove(self._current_output_path)
                    logger.info(f"Cleaned up incomplete file: {self._current_output_path}")
                except Exception as e:
                    logger.warning(f"Could not remove incomplete file: {e}")
                self._current_output_path = None
            
            # Clean up any tracked incomplete files
            for file_path in self._incomplete_files:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.info(f"Cleaned up incomplete file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Could not remove: {e}")
            self._incomplete_files.clear()
            
            # Clean up temp directory for any orphaned files
            import tempfile
            temp_dir = tempfile.gettempdir()
            patterns = [
                os.path.join(temp_dir, "~$*.doc*"),  # Word temp files
                os.path.join(temp_dir, "~$*.xls*"),  # Excel temp files  
                os.path.join(temp_dir, "~$*.ppt*"),  # PowerPoint temp files
            ]
            
            for pattern in patterns:
                for temp_file in glob.glob(pattern):
                    try:
                        # Only delete recent files (created in last 5 minutes)
                        if os.path.getmtime(temp_file) > time.time() - 300:
                            os.remove(temp_file)
                            logger.debug(f"Cleaned up temp file: {temp_file}")
                    except Exception:
                        pass
                        
        except Exception as e:
            logger.warning(f"Cleanup incomplete files error: {e}")

    def _kill_office_processes(self):
        """Kill Office processes that may be hung.
        T2: Parallel execution — O(5s) wall-clock instead of O(3×5s)."""
        try:
            import subprocess
            from concurrent.futures import ThreadPoolExecutor

            def _kill(proc_name):
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/IM', proc_name],
                        capture_output=True,
                        timeout=5
                    )
                except Exception:
                    pass

            with ThreadPoolExecutor(max_workers=3) as pool:
                futs = [pool.submit(_kill, p) for p in
                        ['EXCEL.EXE', 'WINWORD.EXE', 'POWERPNT.EXE']]
                for f in futs:
                    try:
                        f.result(timeout=6)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Kill office processes error: {e}")

    def reset(self):
        """Reset stop flag."""
        self._stop_requested = False
        self._stop_event.clear()
        self._current_converter = None
        self._current_output_path = None
        self._incomplete_files.clear()  # works for both set and list

    def convert_batch(self, files: List[ConversionFile],
                      options: ConversionOptions,
                      output_folder: Optional[str] = None):
        """Convert a batch of files."""
        import pythoncom
        pythoncom.CoInitialize()
        start_watchdog()

        total = len(files)

        try:
            for i, conv_file in enumerate(files):
                if self._stop_requested:
                    break
    
                conv_file.status = "converting"
                start_time = time.time()
    
                # Determine output path
                if output_folder:
                    pdf_name = Path(conv_file.path).stem + ".pdf"
                    output_path = os.path.join(output_folder, pdf_name)
                else:
                    output_path = str(Path(conv_file.path).with_suffix(".pdf"))
    
                conv_file.output_path = output_path
                
                # Track current output for cleanup on force stop
                self._current_output_path = output_path
                self._incomplete_files.add(output_path)  # T4: set.add O(1)
    
                # Progress callback
                if self.on_progress:
                    try:
                        self.on_progress(i, total, conv_file.filename)
                    except Exception:
                        pass
    
                try:
                    success = self._convert_single(conv_file, options)
                    conv_file.duration = time.time() - start_time
                    
                    record_watchdog_conversion(success, conv_file.duration)
    
                    if success:
                        conv_file.status = "completed"
                        # T4: set.discard O(1) instead of list.remove O(N)
                        self._incomplete_files.discard(output_path)
                        self._current_output_path = None
                        
                        # T1: batch write — no commit per file
                        self._db.batch_add_recent(conv_file.path)
                        self._db.batch_log(
                            conv_file.path, output_path, "completed", conv_file.duration
                        )
                    else:
                        conv_file.status = "failed"
                        self._incomplete_files.discard(output_path)
                        self._db.batch_log(
                            conv_file.path, output_path, "failed", conv_file.duration
                        )
    
                    if self.on_file_complete:
                        try:
                            self.on_file_complete(conv_file)
                        except Exception:
                            pass
    
                except Exception as e:
                    conv_file.status = "failed"
                    conv_file.error = str(e)
                    conv_file.duration = time.time() - start_time
                    
                    record_watchdog_conversion(False, conv_file.duration)
    
                    if self.on_error:
                        try:
                            self.on_error(conv_file, e)
                        except Exception:
                            pass
    
                    self._db.batch_log(
                        conv_file.path, output_path, f"error: {e}", conv_file.duration
                    )

        finally:
            # T1: Single flush for all batch writes — O(1) fsync
            try:
                self._db.flush()
            except Exception:
                pass
            stop_watchdog()
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def _convert_single(self, conv_file: ConversionFile,
                        options: ConversionOptions) -> bool:
        """Convert a single file."""
        # Check stop before starting
        if self._stop_requested:
            return False
            
        # get_converter_for_file returns a CLASS, not an instance!
        converter_class = get_converter_for_file(conv_file.path)
        if not converter_class:
            logger.error(f"No converter found for: {conv_file.path}")
            return False

        # Create instance of the converter
        converter = converter_class()
        self._current_converter = converter  # Track for force stop

        try:
            # Check stop again before initialization
            if self._stop_requested:
                return False
                
            # Initialize COM application
            if not converter.initialize():
                logger.error(f"Failed to initialize converter for: {conv_file.path}")
                return False

            # Use com_quality property for correct COM param mapping
            excel_quality = options.com_quality
            
            # Override: scan_mode with high DPI forces quality=0 for best source
            if options.scan_mode and options.quality_dpi >= 250:
                excel_quality = 0
            
            # M4: Check by capability, not class name — robust to renames
            success = False
            if options.sheet_indices:
                import inspect
                sig = inspect.signature(converter.convert)
                if 'sheet_indices' in sig.parameters:
                    success = converter.convert(
                        conv_file.path,
                        conv_file.output_path,
                        excel_quality,
                        options.sheet_indices
                    )
                else:
                    success = converter.convert(
                        conv_file.path,
                        conv_file.output_path,
                        excel_quality
                    )
            else:
                success = converter.convert(
                    conv_file.path,
                    conv_file.output_path,
                    excel_quality
                )

            # Cleanup converter
            converter.cleanup()

            if success and conv_file.output_path:
                # Post-processing
                self._apply_post_processing(conv_file.output_path, options)

            return success

        except Exception as e:
            logger.error(f"Conversion error: {e}")
            # P2: Guard cleanup — converter may be dead after taskkill
            try:
                if converter and hasattr(converter, 'cleanup'):
                    converter.cleanup()
            except Exception:
                pass
            raise

    def _apply_post_processing(self, pdf_path: str, options: ConversionOptions):
        """Apply post-processing to PDF."""
        if not get_fitz():
            return

        try:
            # Page extraction
            if options.page_range:
                page_indices = parse_page_range(options.page_range)
                if page_indices:
                    extract_pdf_pages(pdf_path, page_indices)

            # Password protection
            if options.password:
                post_process_pdf(pdf_path, password=options.password)

            # Scan mode (rasterize) - use quality_dpi from options
            if options.scan_mode:
                rasterize_pdf(pdf_path, dpi=options.quality_dpi)

            # Auto-compress based on quality preset
            compress_level = options.compress_level
            if options.auto_compress and compress_level:
                try:
                    from office_converter.core.pdf.compression import compress_pdf
                    original_size = os.path.getsize(pdf_path)
                    success, ratio = compress_pdf(pdf_path, pdf_path, quality=compress_level)
                    if success and ratio > 1.0:
                        new_size = os.path.getsize(pdf_path)
                        logger.info(
                            f"Auto-compressed ({compress_level}): "
                            f"{original_size/1024:.0f}KB → {new_size/1024:.0f}KB "
                            f"(-{ratio:.1f}%)"
                        )
                    elif success:
                        logger.info("Auto-compress: file already optimal")
                except Exception as e:
                    logger.warning(f"Auto-compress failed (continuing): {e}")
        except Exception as e:
            logger.error(f"Post-processing error: {e}")
