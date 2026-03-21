"""
PowerPoint Converter - Converts presentations to PDF using COM automation.
Upgraded with same pattern as Word:
- 2 fallback export methods (SaveAs → ExportAsFixedFormat2)
- File validation (size, lock, disk space)
- Move retry with 5 attempts
- Metrics logging (size + duration)
- atexit crash temp cleanup
"""

import os
import time
import logging
import shutil
import gc
import uuid
import atexit
import threading
from typing import Optional, Callable


from .base import BaseConverter
from ..utils.com_pool import get_pool

logger = logging.getLogger(__name__)

# PowerPoint constants
ppSaveAsPDF = 32
ppFixedFormatTypePDF = 2  # For ExportAsFixedFormat fallback

# Size limits
MAX_FILE_SIZE_MB = 500
WARN_FILE_SIZE_MB = 100

# Track active temp files for crash cleanup
_active_temp_files: list = []
_temp_lock = threading.Lock()


def _cleanup_ppt_temps():
    """atexit handler to clean orphaned temp files."""
    with _temp_lock:
        for f in _active_temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        _active_temp_files.clear()


atexit.register(_cleanup_ppt_temps)


class PPTConverter(BaseConverter):
    """Converter for PowerPoint presentations (.pptx, .ppt, .pptm, .ppsx, .pps)."""

    SUPPORTED_EXTENSIONS = [".pptx", ".ppt", ".pptm", ".ppsx", ".pps"]

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        super().__init__(log_callback, progress_callback)
        self._ppt = None
        self._use_pool = True

    def initialize(self) -> bool:
        """Get PowerPoint COM from pool."""
        try:
            from .base import ensure_com_initialized
            self._com_owned = ensure_com_initialized()

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

    def _is_ppt_alive(self) -> bool:
        """Check if PowerPoint COM object is still connected.

        A dead COM proxy is non-None but throws -2147220995
        ('Object is not connected to server') on any property access.
        """
        if not self._ppt:
            return False
        try:
            _ = self._ppt.Name  # Lightweight probe
            return True
        except Exception:
            logger.warning("PowerPoint COM instance is dead, will reconnect")
            self._ppt = None
            return False

    def cleanup(self):
        """Release PowerPoint resources."""
        if not self._use_pool and self._ppt:
            try:
                self._ppt.Quit()
            except Exception as e:
                logger.debug(f"PPT quit error: {e}")
            self._ppt = None

        from .base import release_com
        release_com()
        logger.info("PowerPoint cleanup done")

    def _validate_input(self, input_path: str) -> Optional[str]:
        """Validate input file. Returns error message or None."""
        if not os.path.exists(input_path):
            return f"File not found: {input_path}"

        try:
            size_bytes = os.path.getsize(input_path)
            size_mb = size_bytes / (1024 * 1024)

            if size_bytes == 0:
                return f"File is empty (0 bytes): {os.path.basename(input_path)}"

            if size_mb > MAX_FILE_SIZE_MB:
                return (f"File too large ({size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB): "
                        f"{os.path.basename(input_path)}")

            if size_mb > WARN_FILE_SIZE_MB:
                logger.warning(f"Large file ({size_mb:.1f}MB): {os.path.basename(input_path)}")
        except OSError as e:
            return f"Cannot read file: {e}"

        # Check file lock
        try:
            with open(input_path, 'rb') as f:
                f.read(1)
        except PermissionError:
            return f"File is locked by another process: {os.path.basename(input_path)}"
        except OSError as e:
            return f"Cannot open file: {e}"

        # Check disk space
        try:
            output_dir = os.path.dirname(os.path.abspath(input_path))
            if output_dir:
                disk_stat = shutil.disk_usage(output_dir)
                needed = os.path.getsize(input_path) * 2
                if disk_stat.free < needed:
                    free_mb = disk_stat.free / (1024 * 1024)
                    return f"Insufficient disk space ({free_mb:.0f}MB free)"
        except Exception:
            pass

        return None

    def convert(self, input_path: str, output_path: str,
                quality: int = 0) -> bool:
        """Convert PowerPoint to PDF with fallback methods."""
        # Pre-flight validation
        validation_error = self._validate_input(input_path)
        if validation_error:
            logger.error(f"Validation failed: {validation_error}")
            return False

        # COM liveness check: dead proxy is non-None but disconnected
        if not self._is_ppt_alive():
            logger.info("PowerPoint COM not alive, (re)initializing...")
            if not self.initialize():
                return False

        presentation = None
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        conversion_start = time.monotonic()

        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        safe_id = uuid.uuid4().hex
        ext = os.path.splitext(input_path)[1].lower()
        com_input_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}{ext}"))
        com_pdf_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}.pdf"))

        # Register temp files for crash cleanup
        with _temp_lock:
            _active_temp_files.extend([com_input_path, com_pdf_path])

        try:
            shutil.copyfile(input_path, com_input_path)

            presentation = self._ppt.Presentations.Open(
                com_input_path,
                ReadOnly=True,
                Untitled=False,
                WithWindow=False
            )

            errors = []

            # Map quality to PPT export intent
            # quality 0 = high (print intent), 1+ = compact (screen intent)
            ppt_intent = 1 if quality == 0 else 2  # 1=ppFixedFormatIntentPrint, 2=ppFixedFormatIntentScreen
            # Method 1: Standard SaveAs PDF
            method_start = time.monotonic()
            try:
                presentation.SaveAs(com_pdf_path, ppSaveAsPDF)
                if os.path.exists(com_pdf_path):
                    duration = time.monotonic() - conversion_start
                    logger.info(
                        f"PPT converted [M1]: {os.path.basename(input_path)} "
                        f"({file_size_mb:.1f}MB, {duration:.1f}s)"
                    )
                    return self._finalize(presentation, com_input_path,
                                          com_pdf_path, output_path)
            except Exception as e:
                d = time.monotonic() - method_start
                errors.append(f"Method 1 (SaveAs, {d:.1f}s): {e}")

            # Method 2: ExportAsFixedFormat (PDF)
            method_start = time.monotonic()
            try:
                presentation.ExportAsFixedFormat(
                    Path=com_pdf_path,
                    FixedFormatType=ppFixedFormatTypePDF,
                    Intent=ppt_intent,  # Use quality-mapped intent
                    FrameSlides=False,
                    RangeType=1  # ppPrintAll
                )
                if os.path.exists(com_pdf_path):
                    duration = time.monotonic() - conversion_start
                    logger.info(
                        f"PPT converted [M2]: {os.path.basename(input_path)} "
                        f"({file_size_mb:.1f}MB, {duration:.1f}s)"
                    )
                    return self._finalize(presentation, com_input_path,
                                          com_pdf_path, output_path)
            except Exception as e:
                d = time.monotonic() - method_start
                errors.append(f"Method 2 (ExportFixed, {d:.1f}s): {e}")

            # Method 3: PrintOut to Microsoft Print to PDF
            method_start = time.monotonic()
            try:
                old_printer = None
                try:
                    old_printer = self._ppt.ActivePrinter
                except Exception:
                    pass

                try:
                    self._ppt.ActivePrinter = "Microsoft Print to PDF"
                except Exception:
                    try:
                        self._ppt.ActivePrinter = "Microsoft Print to PDF on Ne00:"
                    except Exception:
                        pass

                presentation.PrintOut(
                    PrintToFile=com_pdf_path
                )
                # PrintOut is async
                for _ in range(10):
                    if os.path.exists(com_pdf_path):
                        break
                    time.sleep(0.5)

                if old_printer:
                    try:
                        self._ppt.ActivePrinter = old_printer
                    except Exception:
                        pass

                if os.path.exists(com_pdf_path):
                    duration = time.monotonic() - conversion_start
                    logger.info(
                        f"PPT converted [M3]: {os.path.basename(input_path)} "
                        f"({file_size_mb:.1f}MB, {duration:.1f}s)"
                    )
                    return self._finalize(presentation, com_input_path,
                                          com_pdf_path, output_path)
            except Exception as e:
                d = time.monotonic() - method_start
                errors.append(f"Method 3 (PrintToPDF, {d:.1f}s): {e}")

            # All methods failed
            total_duration = time.monotonic() - conversion_start
            error_summary = "\n".join(errors)
            logger.error(
                f"All PPT export methods failed "
                f"({file_size_mb:.1f}MB, {total_duration:.1f}s):\n{error_summary}"
            )

            try:
                presentation.Close()
            except Exception:
                pass

            return False

        except Exception as e:
            duration = time.monotonic() - conversion_start
            logger.error(
                f"PPT conversion failed ({file_size_mb:.1f}MB, {duration:.1f}s): {e}"
            )
            if presentation:
                try:
                    presentation.Close()
                except Exception:
                    pass
            return False
        finally:
            # Only remove temp files that still exist
            # Note: com_pdf_path may have been moved by _finalize already
            for temp_file in [com_input_path]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception:
                    pass
            # com_pdf_path: only remove if _finalize didn't move it
            try:
                if os.path.exists(com_pdf_path):
                    os.remove(com_pdf_path)
            except Exception:
                pass
            with _temp_lock:
                for f in [com_input_path, com_pdf_path]:
                    try:
                        _active_temp_files.remove(f)
                    except ValueError:
                        pass
            gc.collect()

    def _finalize(self, presentation, com_input_path: str,
                  com_pdf_path: str, output_path: str) -> bool:
        """Close presentation, move PDF to final output, cleanup temp."""
        try:
            presentation.Close()
        except Exception:
            pass

        # Retry move with 5 attempts
        for attempt in range(5):
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                shutil.move(com_pdf_path, output_path)
                break
            except (PermissionError, OSError):
                if attempt < 4:
                    time.sleep(0.5)
                else:
                    raise

        # Cleanup temp input
        try:
            if os.path.exists(com_input_path):
                os.remove(com_input_path)
        except Exception:
            pass

        return True
