"""
Excel Converter - Converts Excel files to PDF using COM automation.
Uses COM Pool for connection reuse and memory optimization.
"""

import os
import time
import logging
import shutil
import gc
import uuid
from typing import Optional, Callable, List

import pythoncom

from .base import BaseConverter
from ..utils.com_pool import get_pool

logger = logging.getLogger(__name__)


class ExcelConverter(BaseConverter):
    """Converter for Excel files (.xlsx, .xls, .xlsm, .xlsb)."""

    SUPPORTED_EXTENSIONS = [".xlsx", ".xls", ".xlsm", ".xlsb"]

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        super().__init__(log_callback, progress_callback)
        self._excel = None
        self._use_pool = False  # Disabled pool due to COM corruption issues

    def initialize(self) -> bool:
        """Get Excel COM from pool."""
        try:
            pythoncom.CoInitialize()
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

    def cleanup(self):
        """Release Excel resources (pool handles actual cleanup)."""
        if not self._use_pool and self._excel:
            try:
                self._excel.Quit()
            except Exception as e:
                logger.debug(f"Excel quit error: {e}")
            self._excel = None

        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

        gc.collect()
        logger.info("Excel cleanup done")

    def convert(self, input_path: str, output_path: str,
                quality: int = 0,
                sheet_indices: Optional[List[int]] = None) -> bool:
        """Convert Excel file to PDF."""
        if not self._excel:
            if not self.initialize():
                return False

        wb = None
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        safe_id = uuid.uuid4().hex

        original_ext = os.path.splitext(input_path)[1].lower()
        if original_ext not in self.SUPPORTED_EXTENSIONS:
            original_ext = ".xlsx"

        com_excel_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}{original_ext}"))
        com_pdf_path = os.path.abspath(os.path.join(temp_dir, f"tmp_{safe_id}.pdf"))

        try:
            shutil.copyfile(input_path, com_excel_path)
            wb = self._excel.Workbooks.Open(com_excel_path)

            if sheet_indices and len(sheet_indices) > 0:
                if len(sheet_indices) == 1:
                    self._safe_export(wb.Worksheets(sheet_indices[0]), com_pdf_path, quality)
                else:
                    self._safe_export(wb, com_pdf_path, quality)
            else:
                self._safe_export(wb, com_pdf_path, quality)

            wb.Close(False)
            wb = None

            # Wait briefly for Excel to release file
            time.sleep(0.3)

            # Retry move operation for locked files
            if os.path.exists(com_pdf_path):
                for attempt in range(5):
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        shutil.move(com_pdf_path, output_path)
                        break
                    except Exception as e:
                        if attempt < 4:
                            time.sleep(0.5)  # Wait for file release
                        else:
                            raise e

            # Cleanup temp Excel file
            for attempt in range(3):
                try:
                    if os.path.exists(com_excel_path):
                        os.remove(com_excel_path)
                    break
                except Exception:
                    time.sleep(0.3)

            return True

        except Exception as e:
            logger.error(f"Excel conversion failed: {e}")
            if wb:
                try:
                    wb.Close(False)
                except Exception:
                    pass
            return False
        finally:
            # Retry cleanup with delays for locked files
            for attempt in range(3):
                try:
                    if os.path.exists(com_pdf_path):
                        os.remove(com_pdf_path)
                    break
                except Exception:
                    time.sleep(0.5)  # Wait for file to be released
            gc.collect()

    def _safe_export(self, obj, path: str, quality: int = 0) -> None:
        """
        Export workbook/sheet to PDF with multiple fallback methods.
        Handles common Excel COM errors with detailed logging.
        """
        # Verify temp folder is writable
        temp_folder = os.path.dirname(path)
        if not os.path.exists(temp_folder):
            try:
                os.makedirs(temp_folder, exist_ok=True)
            except Exception as e:
                raise Exception(f"Cannot create temp folder: {temp_folder}, {e}")

        # Test write permission
        test_file = os.path.join(temp_folder, f"_write_test_{uuid.uuid4().hex}.tmp")
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            raise Exception(f"Temp folder not writable: {temp_folder}, {e}")

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
                return
        except Exception as e:
            errors.append(f"Method 1 (Standard): {str(e)}")

        # Attempt 2: Ignore Print Areas
        try:
            obj.ExportAsFixedFormat(0, path, Quality=quality,
                                    IncludeDocProperties=False,
                                    IgnorePrintAreas=True,
                                    OpenAfterPublish=False)
            if os.path.exists(path):
                return
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
                return
        except Exception as e:
            errors.append(f"Method 3 (ClearPrintArea): {str(e)}")

        # Attempt 4: SaveAs PDF
        try:
            obj.SaveAs(Filename=path, FileFormat=57)
            if os.path.exists(path):
                return
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
                    return
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
                    return
                new_wb.Close(False)
        except Exception as e:
            errors.append(f"Method 6 (RawCopy): {str(e)}")

        # Attempt 7: Print to Microsoft Print to PDF
        try:
            app = obj.Application

            # Get current active printer
            old_printer = None
            try:
                old_printer = app.ActivePrinter
            except:
                pass

            # Set Microsoft Print to PDF
            try:
                app.ActivePrinter = "Microsoft Print to PDF"
            except:
                try:
                    app.ActivePrinter = "Microsoft Print to PDF on Ne00:"
                except:
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
                except:
                    pass

            if os.path.exists(path):
                return
        except Exception as e:
            errors.append(f"Method 7 (PrintToPDF): {str(e)}")

        # Log all errors for debugging
        error_summary = "\n".join(errors)
        logger.error(f"All export methods failed:\n{error_summary}")
        raise Exception(f"All 7 export methods failed for: {path}\nDetails:\n{error_summary}")
