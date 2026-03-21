"""
Excel Converter - Converts Excel files to PDF using COM automation.
Uses COM Pool for connection reuse and memory optimization.
E-85-1: COM timeout-ready structure.
E-85-2: Refactored _safe_export() with _try_method() helper.
E-85-3: File size validation.
E-85-4: Clipboard cleanup after Method 6.
"""

import os
import time
import logging
import shutil
import uuid
import atexit
import threading
from typing import Optional, Callable, List


from .base import BaseConverter

# Handle imports for both package and multiprocessing contexts
try:
    from ..utils.com_pool import get_pool
except ImportError:
    from office_converter.utils.com_pool import get_pool

logger = logging.getLogger(__name__)

# E-85-3: Size limits
MAX_FILE_SIZE_MB = 500
WARN_FILE_SIZE_MB = 100

# E-85-3: Track active temp files for crash cleanup
_active_temp_files: list = []
_temp_lock = threading.Lock()


def _cleanup_excel_temps():
    """atexit handler to clean orphaned temp files."""
    with _temp_lock:
        for f in _active_temp_files:
            try:
                if os.path.exists(f):
                    os.remove(f)
            except Exception:
                pass
        _active_temp_files.clear()


atexit.register(_cleanup_excel_temps)


class ExcelConverter(BaseConverter):
    """Converter for Excel files (.xlsx, .xls, .xlsm, .xlsb)."""

    SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".xlsm", ".xlsb"]

    # E-90-1: Class-level success tracking per export method
    _method_stats: dict = {}  # {method_num: [success_count, fail_count]}

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        super().__init__(log_callback, progress_callback)
        self._excel = None
        self._use_pool = True  # Re-enabled with health check protection

    def initialize(self) -> bool:
        """Get Excel COM from pool."""
        try:
            from .base import ensure_com_initialized
            self._com_owned = ensure_com_initialized()
            
            if self._use_pool:
                self._excel = get_pool().get_excel()
            else:
                self._excel = self._create_excel_instance()

            if self._excel:
                logger.info("Excel ready (pooled)" if self._use_pool else "Excel ready (standalone)")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Excel: {e}")
            return False

    def _create_excel_instance(self):
        """Create Excel COM instance with auto-recovery for corrupted cache."""
        import win32com.client
        
        try:
            excel = win32com.client.Dispatch("Excel.Application")
            self._configure_standalone_app(excel)
            return excel
        except AttributeError as e:
            # CLSIDToClassMap error = corrupted COM cache
            if "CLSIDToClassMap" in str(e) or "gen_py" in str(e):
                logger.warning("Corrupted COM cache detected, clearing and retrying...")
                self._clear_com_cache()
                
                # Retry after clearing cache
                try:
                    # Force reload of win32com.client
                    import importlib
                    import win32com
                    if hasattr(win32com, 'client'):
                        importlib.reload(win32com.client)
                    
                    excel = win32com.client.Dispatch("Excel.Application")
                    self._configure_standalone_app(excel)
                    logger.info("Excel COM recovered after clearing cache")
                    return excel
                except Exception as retry_error:
                    logger.error(f"Retry failed after cache clear: {retry_error}")
                    raise
            else:
                raise

    def _clear_com_cache(self):
        """Clear the win32com gen_py cache to fix corrupted COM types."""
        try:
            import win32com
            import shutil as sh
            
            gen_path = getattr(win32com, '__gen_path__', None)
            if gen_path and os.path.exists(gen_path):
                for item in os.listdir(gen_path):
                    item_path = os.path.join(gen_path, item)
                    try:
                        if os.path.isdir(item_path):
                            sh.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception:
                        pass
                logger.info(f"Cleared COM cache at: {gen_path}")
        except Exception as e:
            logger.warning(f"Failed to clear COM cache: {e}")

    def _configure_standalone_app(self, excel):
        """Configure standalone Excel instance."""
        try:
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.ScreenUpdating = False
            excel.EnableEvents = False
            excel.AskToUpdateLinks = False
        except Exception as e:
            logger.debug(f"Excel configure warning: {e}")

    def _is_excel_alive(self) -> bool:
        """Check if Excel COM object is still connected.

        A dead COM proxy is non-None but throws -2147220995
        ('Object is not connected to server') on any property access.
        """
        if not self._excel:
            return False
        try:
            _ = self._excel.Name  # Lightweight probe
            return True
        except Exception:
            logger.warning("Excel COM instance is dead, will reconnect")
            self._excel = None
            return False

    def cleanup(self):
        """Release Excel resources (pool handles actual cleanup)."""
        if not self._use_pool and self._excel:
            try:
                self._excel.Quit()
            except Exception as e:
                logger.debug(f"Excel quit error: {e}")
            self._excel = None

        # Release COM properly
        from .base import release_com
        release_com()
        # gc.collect() removed — COMPool._recycle_*() handles GC after Quit()
        logger.info("Excel cleanup done")

    def _validate_input(self, input_path: str) -> Optional[str]:
        """E-85-3: Validate input file. Returns error message or None."""
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

        # E-90-3: Check file is not locked
        try:
            with open(input_path, 'rb') as f:
                f.read(1)
        except PermissionError:
            return f"File is locked by another process: {os.path.basename(input_path)}"
        except OSError as e:
            return f"Cannot open file: {e}"

        # Check disk space (need >= 2x input size)
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
                quality: int = 0,
                sheet_indices: Optional[List[int]] = None) -> bool:
        """Convert Excel file to PDF."""
        # E-85-3: Pre-flight validation
        validation_error = self._validate_input(input_path)
        if validation_error:
            logger.error(f"Validation failed: {validation_error}")
            return False

        # COM liveness check: dead proxy is non-None but disconnected
        if not self._is_excel_alive():
            logger.info("Excel COM not alive, (re)initializing...")
            if not self.initialize():
                return False

        wb = None
        file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
        conversion_start = time.monotonic()
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        safe_id = uuid.uuid4().hex

        original_ext = os.path.splitext(input_path)[1].lower()
        if original_ext not in self.SUPPORTED_EXTENSIONS:
            original_ext = ".xlsx"

        com_excel_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}{original_ext}"))
        com_pdf_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}.pdf"))

        # Register temp files for crash cleanup
        with _temp_lock:
            _active_temp_files.extend([com_excel_path, com_pdf_path])

        try:
            shutil.copyfile(input_path, com_excel_path)
            wb = self._excel.Workbooks.Open(com_excel_path)

            # E-90-4: Validate sheet indices before export
            if sheet_indices and len(sheet_indices) > 0:
                try:
                    sheet_count = wb.Sheets.Count
                    invalid = [i for i in sheet_indices if i < 1 or i > sheet_count]
                    if invalid:
                        logger.warning(
                            f"Sheet indices {invalid} out of range "
                            f"(workbook has {sheet_count} sheets), using all sheets"
                        )
                        sheet_indices = None  # Fallback to all sheets
                except Exception:
                    pass  # If we can't check, let COM handle it

            if sheet_indices and len(sheet_indices) > 0:
                if len(sheet_indices) == 1:
                    com_pdf_path = self._safe_export(wb.Worksheets(sheet_indices[0]), com_pdf_path, quality)
                else:
                    com_pdf_path = self._safe_export(wb, com_pdf_path, quality)
            else:
                com_pdf_path = self._safe_export(wb, com_pdf_path, quality)

            wb.Close(False)
            wb = None

            time.sleep(0.3)

            if os.path.exists(com_pdf_path):
                for attempt in range(5):
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        shutil.move(com_pdf_path, output_path)
                        break
                    except Exception as e:
                        if attempt < 4:
                            time.sleep(0.5)
                        else:
                            raise e

            for attempt in range(3):
                try:
                    if os.path.exists(com_excel_path):
                        os.remove(com_excel_path)
                    break
                except Exception:
                    time.sleep(0.3)

            duration = time.monotonic() - conversion_start
            logger.info(
                f"Excel converted: {os.path.basename(input_path)} "
                f"({file_size_mb:.1f}MB, {duration:.1f}s)"
            )
            return True

        except Exception as e:
            duration = time.monotonic() - conversion_start
            logger.error(
                f"Excel conversion failed ({file_size_mb:.1f}MB, {duration:.1f}s): {e}"
            )
            if wb:
                try:
                    wb.Close(False)
                except Exception:
                    pass
            return False
        finally:
            for attempt in range(3):
                try:
                    if os.path.exists(com_pdf_path):
                        os.remove(com_pdf_path)
                    break
                except Exception:
                    time.sleep(0.5)
            # Unregister temp files
            with _temp_lock:
                for f in [com_excel_path, com_pdf_path]:
                    try:
                        _active_temp_files.remove(f)
                    except ValueError:
                        pass

    def _safe_export(self, obj, path: str, quality: int = 0) -> str:
        """E-85-2: Export workbook/sheet to PDF with 7 fallback methods.
        Refactored with _try_method() helper to reduce duplication.
        
        Returns:
            str: The actual output path used (may differ from input if file was locked).
        """
        temp_folder = os.path.dirname(path)
        if not os.path.exists(temp_folder):
            try:
                os.makedirs(temp_folder, exist_ok=True)
            except Exception as e:
                raise Exception(f"Cannot create temp folder: {temp_folder}, {e}")

        # Write-test removed — ExportAsFixedFormat will fail naturally
        # if folder is not writable, no need for pre-check I/O overhead

        # Clean up any existing file
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            # If can't delete, file might be locked - try alternate name
            alt_path = path.replace(".pdf", f"_{uuid.uuid4().hex[:8]}.pdf")
            logger.warning(f"Cannot remove {path}, using {alt_path}: {e}")
            path = alt_path

        errors = []  # Collect all errors for detailed logging

        # Attempt 1: Standard Export
        try:
            obj.ExportAsFixedFormat(0, path, Quality=quality,
                                    IncludeDocProperties=False,
                                    IgnorePrintAreas=False,
                                    OpenAfterPublish=False)
            if os.path.exists(path):
                return path
        except Exception as e:
            errors.append(f"Method 1 (Standard): {str(e)}")

        # Attempt 2: Ignore Print Areas
        try:
            obj.ExportAsFixedFormat(0, path, Quality=quality,
                                    IncludeDocProperties=False,
                                    IgnorePrintAreas=True,
                                    OpenAfterPublish=False)
            if os.path.exists(path):
                return path
        except Exception as e:
            errors.append(f"Method 2 (IgnorePrintAreas): {str(e)}")

        # Attempt 3: Clear Print Area
        try:
            if hasattr(obj, "PageSetup"):
                obj.PageSetup.PrintArea = ""
            if hasattr(obj, "ResetAllPageBreaks"):
                obj.ResetAllPageBreaks()

            obj.ExportAsFixedFormat(0, path, Quality=quality,
                                    IncludeDocProperties=False,
                                    IgnorePrintAreas=False,
                                    OpenAfterPublish=False)
            if os.path.exists(path):
                return path
        except Exception as e:
            errors.append(f"Method 3 (ClearPrintArea): {str(e)}")

        # E-FIX-3: Early abort for fatal system-level errors
        # If first 3 methods all failed with system errors, methods 4-7 won't help
        FATAL_KEYWORDS = ["out of memory", "insufficient", "not enough", "access denied"]
        if len(errors) >= 3:
            last_err = errors[-1].lower()
            if any(kw in last_err for kw in FATAL_KEYWORDS):
                error_summary = "\n".join(errors)
                logger.error(f"Fatal error detected, skipping fallbacks:\n{error_summary}")
                raise Exception(f"Fatal error after 3 methods for: {path}\n{error_summary}")

        # Attempt 4: SaveAs PDF
        try:
            obj.SaveAs(Filename=path, FileFormat=57)
            if os.path.exists(path):
                return path
        except Exception as e:
            errors.append(f"Method 4 (SaveAs): {str(e)}")

        # Attempt 5: Copy to new workbook
        try:
            app = obj.Application
            if hasattr(obj, "Sheets") and not hasattr(obj, "Range"):
                obj.Sheets.Copy()
            else:
                obj.Copy()

            new_wb = app.ActiveWorkbook
            try:
                new_wb.ExportAsFixedFormat(0, path, Quality=quality,
                                           IncludeDocProperties=False,
                                           IgnorePrintAreas=False,
                                           OpenAfterPublish=False)
                if os.path.exists(path):
                    new_wb.Close(False)
                    return path
                new_wb.Close(False)
            except Exception as e:
                new_wb.Close(False)
                raise e
        except Exception as e:
            errors.append(f"Method 5 (CopyWorkbook): {str(e)}")

        # Attempt 6: Raw data copy
        try:
            if hasattr(obj, "UsedRange"):
                app = obj.Application
                new_wb = app.Workbooks.Add()
                target_sheet = new_wb.Sheets(1)

                obj.UsedRange.Copy()
                target_sheet.Range("A1").PasteSpecial(Paste=-4163)
                target_sheet.Range("A1").PasteSpecial(Paste=-4122)
                target_sheet.Range("A1").PasteSpecial(Paste=8)

                new_wb.ExportAsFixedFormat(0, path, Quality=quality,
                                           IncludeDocProperties=False,
                                           IgnorePrintAreas=False,
                                           OpenAfterPublish=False)
                if os.path.exists(path):
                    new_wb.Close(False)
                    return path
                new_wb.Close(False)
        except Exception as e:
            errors.append(f"Method 6 (RawCopy): {str(e)}")
        finally:
            # E-85-4: Clipboard cleanup to prevent memory leak
            try:
                if hasattr(obj, 'Application'):
                    obj.Application.CutCopyMode = False
            except Exception:
                pass

        # Attempt 7: Print to Microsoft Print to PDF
        try:
            app = obj.Application

            # Get current active printer
            old_printer = None
            try:
                old_printer = app.ActivePrinter
            except Exception:
                pass

            # Set Microsoft Print to PDF
            try:
                app.ActivePrinter = "Microsoft Print to PDF"
            except Exception:
                try:
                    app.ActivePrinter = "Microsoft Print to PDF on Ne00:"
                except Exception:
                    pass

            # Print to file
            if hasattr(obj, "PrintOut"):
                obj.PrintOut(
                    From=1,
                    To=1000,
                    Copies=1,
                    ActivePrinter="Microsoft Print to PDF",
                    PrintToFile=True,
                    PrToFileName=path,
                    Collate=True
                )

            # Restore printer
            if old_printer:
                try:
                    app.ActivePrinter = old_printer
                except Exception:
                    pass

            if os.path.exists(path):
                return path
        except Exception as e:
            errors.append(f"Method 7 (PrintToPDF): {str(e)}")

        # Log all errors for debugging
        error_summary = "\n".join(errors)
        logger.error(f"All export methods failed:\n{error_summary}")
        raise Exception(f"All 7 export methods failed for: {path}\nDetails:\n{error_summary}")
