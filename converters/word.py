"""
Word Converter - Converts Word documents to PDF using COM automation.
W-FIX-1: 3 fallback export methods (Export, SaveAs2, PrintToPDF).
W-FIX-2: Move retry with 5 attempts (matching Excel pattern).
W-85-1: COM timeout wrapper.
W-85-2: File size validation.
W-85-3: Error metrics (file size + duration).
W-85-4: Password-protected file detection.
W-85-5: Macro security hardening.
W-85-6: Crash temp cleanup via atexit.
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

# Word constants
wdExportFormatPDF = 17
wdExportOptimizeForPrint = 0
wdExportOptimizeForOnScreen = 1
wdFormatPDF = 17  # For SaveAs2 fallback

# W-85-6: Track active temp files for crash cleanup
_active_temp_files: list = []
_temp_lock = threading.Lock()

# W-85-2: Size limits
MAX_FILE_SIZE_MB = 500  # Skip files larger than this
WARN_FILE_SIZE_MB = 100  # Log warning for files larger than this

# W-85-1: COM operation timeout
COM_TIMEOUT_SECONDS = 120  # 2 minutes max per COM operation


def _cleanup_word_temps():
    """W-85-6: atexit handler to clean orphaned temp files."""
    with _temp_lock:
        for f in _active_temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        _active_temp_files.clear()


atexit.register(_cleanup_word_temps)


def _register_temp(path: str) -> None:
    """Register a temp file for crash cleanup."""
    with _temp_lock:
        _active_temp_files.append(path)


def _unregister_temp(path: str) -> None:
    """Unregister a temp file after successful cleanup."""
    with _temp_lock:
        try:
            _active_temp_files.remove(path)
        except ValueError:
            pass


class WordConverter(BaseConverter):
    """Converter for Word documents (.docx, .doc, .docm, .rtf)."""

    SUPPORTED_EXTENSIONS = [".docx", ".doc", ".docm", ".rtf"]

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        super().__init__(log_callback, progress_callback)
        self._word = None
        self._use_pool = True

    def initialize(self) -> bool:
        """Get Word COM from pool."""
        try:
            from .base import ensure_com_initialized
            self._com_owned = ensure_com_initialized()

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
        try:
            self._word.Visible = False
            self._word.DisplayAlerts = 0
            self._word.Options.CheckSpellingAsYouType = False
            self._word.Options.CheckGrammarAsYouType = False
            self._word.AutomationSecurity = 3
        except Exception as e:
            logger.debug(f"Word configure warning: {e}")

    def cleanup(self):
        """Release Word resources."""
        if not self._use_pool and self._word:
            try:
                self._word.Quit()
            except Exception as e:
                logger.debug(f"Word quit error: {e}")
            self._word = None

        from .base import release_com
        release_com()
        logger.info("Word cleanup done")

    def _validate_input(self, input_path: str) -> Optional[str]:
        """W-85-2 + W-85-4: Validate input file before conversion.

        Returns None if valid, or error message string if invalid.
        """
        # Check file exists
        if not os.path.exists(input_path):
            return f"File not found: {input_path}"

        # Check file size
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

        # W-90-2: Check file is not locked by another process
        try:
            with open(input_path, 'rb') as f:
                f.read(1)  # Read 1 byte to verify access
        except PermissionError:
            return f"File is locked by another process: {os.path.basename(input_path)}"
        except OSError as e:
            return f"Cannot open file: {e}"

        # W-85-4: Check password protection for .docx (ZIP-based)
        ext = os.path.splitext(input_path)[1].lower()
        if ext == ".docx":
            try:
                import zipfile
                if zipfile.is_zipfile(input_path):
                    with zipfile.ZipFile(input_path, 'r') as zf:
                        if 'EncryptedPackage' in zf.namelist():
                            return (f"File is password-protected: "
                                    f"{os.path.basename(input_path)}")
            except Exception:
                pass

        # W-90-2: Check output disk space (need >= 2x input size)
        try:
            output_dir = os.path.dirname(os.path.abspath(input_path))
            if output_dir:
                disk_stat = shutil.disk_usage(output_dir)
                needed = os.path.getsize(input_path) * 2
                if disk_stat.free < needed:
                    free_mb = disk_stat.free / (1024 * 1024)
                    return f"Insufficient disk space ({free_mb:.0f}MB free)"
        except Exception:
            pass  # Non-critical, don't block conversion

        return None  # Valid

    def convert(self, input_path: str, output_path: str,
                quality: int = 0) -> bool:
        """Convert Word document to PDF with fallback methods."""
        # W-85-2: Pre-flight validation
        validation_error = self._validate_input(input_path)
        if validation_error:
            logger.error(f"Validation failed: {validation_error}")
            return False

        if not self._word:
            if not self.initialize():
                return False

        doc = None
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        conversion_start = time.monotonic()

        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        safe_id = uuid.uuid4().hex
        ext = os.path.splitext(input_path)[1].lower()
        com_input_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}{ext}"))
        com_pdf_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}.pdf"))

        # W-85-6: Register temp files for crash cleanup
        _register_temp(com_input_path)
        _register_temp(com_pdf_path)

        try:
            shutil.copyfile(input_path, com_input_path)

            # W-85-5: Disable macros before opening
            try:
                self._word.WordBasic.DisableAutoMacros(1)
            except Exception:
                pass  # Not all Word versions support this

            # W-90-3: Try standard open first, then repair if corrupt
            try:
                doc = self._word.Documents.Open(
                    com_input_path,
                    ConfirmConversions=False,
                    ReadOnly=True,
                    AddToRecentFiles=False,
                    Visible=False,
                    NoEncodingDialog=True
                )
            except Exception as open_err:
                logger.warning(f"Standard open failed, trying repair: {open_err}")
                try:
                    doc = self._word.Documents.Open(
                        com_input_path,
                        ConfirmConversions=False,
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        Visible=False,
                        NoEncodingDialog=True,
                        OpenAndRepair=True
                    )
                    logger.info("Document opened with repair mode")
                except Exception as repair_err:
                    logger.error(f"Repair open also failed: {repair_err}")
                    raise

            optimize = (wdExportOptimizeForPrint if quality == 0
                        else wdExportOptimizeForOnScreen)
            errors = []

            # Method 1: Standard ExportAsFixedFormat
            method_start = time.monotonic()
            try:
                doc.ExportAsFixedFormat(
                    OutputFileName=com_pdf_path,
                    ExportFormat=wdExportFormatPDF,
                    OptimizeFor=optimize,
                    CreateBookmarks=1,
                    DocStructureTags=True,
                    BitmapMissingFonts=True
                )
                if os.path.exists(com_pdf_path):
                    duration = time.monotonic() - conversion_start
                    # W-85-3: Metrics
                    logger.info(
                        f"Word converted [M1]: {os.path.basename(input_path)} "
                        f"({file_size_mb:.1f}MB, {duration:.1f}s)"
                    )
                    return self._finalize(doc, com_input_path, com_pdf_path,
                                          output_path)
            except Exception as e:
                d = time.monotonic() - method_start
                errors.append(f"Method 1 (Export, {d:.1f}s): {e}")

            # Method 2: SaveAs2 with wdFormatPDF
            method_start = time.monotonic()
            try:
                doc.SaveAs2(FileName=com_pdf_path, FileFormat=wdFormatPDF)
                if os.path.exists(com_pdf_path):
                    duration = time.monotonic() - conversion_start
                    logger.info(
                        f"Word converted [M2]: {os.path.basename(input_path)} "
                        f"({file_size_mb:.1f}MB, {duration:.1f}s)"
                    )
                    return self._finalize(doc, com_input_path, com_pdf_path,
                                          output_path)
            except Exception as e:
                d = time.monotonic() - method_start
                errors.append(f"Method 2 (SaveAs2, {d:.1f}s): {e}")

            # Method 3: PrintOut to Microsoft Print to PDF
            method_start = time.monotonic()
            try:
                old_printer = None
                try:
                    old_printer = self._word.ActivePrinter
                except Exception:
                    pass

                try:
                    self._word.ActivePrinter = "Microsoft Print to PDF"
                except Exception:
                    try:
                        self._word.ActivePrinter = "Microsoft Print to PDF on Ne00:"
                    except Exception:
                        pass

                doc.PrintOut(
                    OutputFileName=com_pdf_path,
                    Item=0,
                    PrintToFile=True
                )
                # PrintOut is async — wait for file
                for _ in range(10):
                    if os.path.exists(com_pdf_path):
                        break
                    time.sleep(0.5)

                if old_printer:
                    try:
                        self._word.ActivePrinter = old_printer
                    except Exception:
                        pass

                if os.path.exists(com_pdf_path):
                    duration = time.monotonic() - conversion_start
                    logger.info(
                        f"Word converted [M3]: {os.path.basename(input_path)} "
                        f"({file_size_mb:.1f}MB, {duration:.1f}s)"
                    )
                    return self._finalize(doc, com_input_path, com_pdf_path,
                                          output_path)
            except Exception as e:
                d = time.monotonic() - method_start
                errors.append(f"Method 3 (PrintToPDF, {d:.1f}s): {e}")

            # All methods failed
            total_duration = time.monotonic() - conversion_start
            error_summary = "\n".join(errors)
            logger.error(
                f"All Word export methods failed "
                f"({file_size_mb:.1f}MB, {total_duration:.1f}s):\n{error_summary}"
            )

            try:
                doc.Close(False)
            except Exception:
                pass

            return False

        except Exception as e:
            duration = time.monotonic() - conversion_start
            logger.error(
                f"Word conversion failed ({file_size_mb:.1f}MB, {duration:.1f}s): {e}"
            )
            if doc:
                try:
                    doc.Close(False)
                except Exception:
                    pass
            return False
        finally:
            # Cleanup temp files
            for temp_file in [com_pdf_path, com_input_path]:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    _unregister_temp(temp_file)
                except Exception:
                    pass
            gc.collect()

    def _finalize(self, doc, com_input_path: str, com_pdf_path: str,
                  output_path: str) -> bool:
        """Close document, move PDF to final output, cleanup temp."""
        try:
            doc.Close(False)
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
            _unregister_temp(com_input_path)
        except Exception:
            pass

        return True
