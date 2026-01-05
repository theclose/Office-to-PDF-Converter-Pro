"""
Office Converter Pro - Refactored Architecture (FIXED)
Version 4.0.1 - Professional Grade with Preview, DnD, Recent Files

HOTFIX CHANGES:
- Fixed fitz import (moved to global scope with fallback)
- Added try/except to all critical functions
- Fixed _show_settings crash when dialogs module missing
- Added error handling for all button callbacks
- Fixed progress_frame packing issue
- Added proper cleanup in preview panel
"""

import os
import sys
import time
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Set, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum, auto

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# Add parent directories to path for imports
ui_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(ui_dir)
root_dir = os.path.dirname(package_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from office_converter.utils.logging_setup import setup_logging
from office_converter.utils.config import Config
from office_converter.utils.com_pool import release_pool
# Lazy: pdf_tools and converters are loaded on-demand
# from office_converter.utils.pdf_tools import ... -> Moved to functions
# from office_converter.converters import ExcelConverter -> Moved to _convert_single

# PDF tools - loaded at module level for preview panel
from office_converter.utils.pdf_tools import (
    post_process_pdf, rasterize_pdf, parse_page_range, extract_pdf_pages, HAS_PYMUPDF
)
from office_converter.converters import get_converter_for_file  # Lightweight lookup only

# Setup logging
logger = setup_logging()

# Drag and drop support - TkinterDnD2 for robust Unicode handling
from office_converter.utils.tkdnd_wrapper import TkDnDWrapper, HAS_TKDND, DND_FILES
from office_converter.utils.dnd_helpers import parse_dropped_paths

if HAS_TKDND:
    logger.info("tkinterdnd2 available - drag-drop enabled with Unicode support")
else:
    logger.warning("tkinterdnd2 not installed - drag drop disabled")

# UI Components
from office_converter.ui.file_tools_ui_v2 import FileToolsDialog

# Import fitz (PyMuPDF) at module level with proper fallback
fitz = None
if HAS_PYMUPDF:
    try:
        import fitz as _fitz
        fitz = _fitz
    except ImportError:
        pass

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

# CustomTkinter theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


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
    """Conversion settings."""
    quality: int = 0  # 0=high, 1=compact, 2=custom
    quality_dpi: int = 300  # only used if quality=2
    scan_mode: bool = False
    password: Optional[str] = None
    page_range: Optional[str] = None
    sheet_indices: Optional[List[int]] = None
    author: Optional[str] = None
    title: Optional[str] = None


# ============================================================================
# DATABASE LAYER (Recent Files) - Now imported from utils
# ============================================================================

from office_converter.utils.recent_files import RecentFilesDB, get_recent_files_db


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
        self._incomplete_files: List[str] = []  # Track incomplete files for cleanup
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
        """Force stop by cleaning up current converter, files and killing Office processes."""
        try:
            # Cleanup current converter if exists
            if self._current_converter:
                try:
                    self._current_converter.cleanup()
                except Exception:
                    pass
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
        """Kill Office application processes that may be hung."""
        try:
            import subprocess
            # Kill common Office processes that might be stuck
            for proc_name in ['EXCEL.EXE', 'WINWORD.EXE', 'POWERPNT.EXE']:
                try:
                    subprocess.run(
                        ['taskkill', '/F', '/IM', proc_name],
                        capture_output=True,
                        timeout=5
                    )
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
        self._incomplete_files.clear()

    def convert_batch(self, files: List[ConversionFile],
                      options: ConversionOptions,
                      output_folder: Optional[str] = None):
        """Convert a batch of files."""
        import pythoncom
        pythoncom.CoInitialize()

        total = len(files)

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
            self._incomplete_files.append(output_path)

            # Progress callback
            if self.on_progress:
                try:
                    self.on_progress(i, total, conv_file.filename)
                except Exception:
                    pass

            try:
                success = self._convert_single(conv_file, options)
                conv_file.duration = time.time() - start_time

                if success:
                    conv_file.status = "completed"
                    # Remove from incomplete list since it's done
                    if output_path in self._incomplete_files:
                        self._incomplete_files.remove(output_path)
                    self._current_output_path = None
                    
                    self._db.add_recent(conv_file.path)
                    self._db.log_conversion(
                        conv_file.path, output_path, "completed", conv_file.duration
                    )
                else:
                    conv_file.status = "failed"
                    # Also remove failed file from incomplete (we don't need to clean it)
                    if output_path in self._incomplete_files:
                        self._incomplete_files.remove(output_path)
                    self._db.log_conversion(
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

                if self.on_error:
                    try:
                        self.on_error(conv_file, e)
                    except Exception:
                        pass

                self._db.log_conversion(
                    conv_file.path, output_path, f"error: {e}", conv_file.duration
                )

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

            # Excel with sheet indices (check by name to avoid eager import)
            if converter.__class__.__name__ == "ExcelConverter" and options.sheet_indices:
                success = converter.convert(
                    conv_file.path,
                    conv_file.output_path,
                    options.quality,
                    options.sheet_indices
                )
            else:
                success = converter.convert(
                    conv_file.path,
                    conv_file.output_path,
                    options.quality
                )

            # Cleanup converter
            converter.cleanup()

            if success and conv_file.output_path:
                # Post-processing
                self._apply_post_processing(conv_file.output_path, options)

            return success

        except Exception as e:
            logger.error(f"Conversion error: {e}")
            # Make sure to cleanup even on error
            try:
                converter.cleanup()
            except Exception:
                pass
            raise

    def _apply_post_processing(self, pdf_path: str, options: ConversionOptions):
        """Apply post-processing to PDF."""
        if not HAS_PYMUPDF:
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

            # Scan mode (rasterize)
            if options.scan_mode:
                rasterize_pdf(pdf_path)
        except Exception as e:
            logger.error(f"Post-processing error: {e}")




# ============================================================================
# FILE LIST COMPONENT
# ============================================================================

class FileListPanel(ctk.CTkFrame):
    """Enhanced file list with drag & drop, selection and type indicators."""

    def __init__(self, parent, on_selection_change: Optional[Callable] = None, 
                 app_instance=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.files: List[ConversionFile] = []
        self.selected_indices: set = set()  # Track selected file indices
        self.anchor_index: int = -1  # For shift-selection
        self.on_selection_change = on_selection_change
        self.app_instance = app_instance  # Store reference to main app for logging

        self._create_widgets()
        self._setup_drag_drop()
        self._setup_keyboard_bindings()

    def _create_widgets(self):
        """Create file list widgets."""
        # Type indicator bar
        self.type_bar = ctk.CTkFrame(self, height=6, corner_radius=3)
        self.type_bar.pack(fill="x", padx=10, pady=(10, 5))

        self.excel_bar = ctk.CTkFrame(self.type_bar, fg_color=FILE_TYPE_COLORS[FileType.EXCEL])
        self.word_bar = ctk.CTkFrame(self.type_bar, fg_color=FILE_TYPE_COLORS[FileType.WORD])
        self.ppt_bar = ctk.CTkFrame(self.type_bar, fg_color=FILE_TYPE_COLORS[FileType.POWERPOINT])

        # Drop zone / File list
        self.drop_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.drop_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.drop_label = ctk.CTkLabel(
            self.drop_frame,
            text="📁 Kéo thả files vào đây\n\n💡 Ctrl+O: Thêm files\n⌫ Delete: Xóa files đã chọn\n🔲 Ctrl+A: Chọn tất cả",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.drop_label.pack(expand=True, pady=30)

        # Use Listbox for proper selection support
        self.file_listbox = tk.Listbox(
            self.drop_frame,
            font=("Consolas", 11),
            selectmode=tk.EXTENDED,  # Allow multiple selection
            bg="#2b2b2b",
            fg="#dcdcdc",
            selectbackground="#1f6aa5",
            selectforeground="white",
            highlightthickness=0,
            borderwidth=0,
            activestyle="none"
        )

        # Stats row
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.count_label = ctk.CTkLabel(
            stats_frame,
            text="0 files",
            font=ctk.CTkFont(weight="bold")
        )
        self.count_label.pack(side="left")

        self.types_label = ctk.CTkLabel(
            stats_frame,
            text="",
            text_color="gray"
        )
        self.types_label.pack(side="left", padx=10)

    def _setup_drag_drop(self):
        """Setup drag and drop support."""
        try:
            from tkinterdnd2 import DND_FILES

            # Check if root supports DnD
            root = self.winfo_toplevel()
            if hasattr(root, 'drop_target_register'):
                self.drop_frame.drop_target_register(DND_FILES)
                self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
                self.drop_label.configure(text="📁 Kéo thả files vào đây\n✅ Drag & Drop đã bật")
        except ImportError:
            logger.info("TkinterDnD2 not available, drag & drop disabled")
        except Exception as e:
            logger.warning(f"Could not setup drag & drop: {e}")

    def _setup_keyboard_bindings(self):
        """Setup keyboard shortcuts for file selection."""
        # Ctrl+A to select all
        self.file_listbox.bind('<Control-a>', self._select_all)
        self.file_listbox.bind('<Control-A>', self._select_all)
        
        # Delete to remove selected
        self.file_listbox.bind('<Delete>', self._delete_selected)
        self.file_listbox.bind('<BackSpace>', self._delete_selected)
        
        # Update selected_indices when selection changes
        self.file_listbox.bind('<<ListboxSelect>>', self._on_listbox_select)

    def _select_all(self, event=None):
        """Select all files."""
        if self.files:
            self.file_listbox.select_set(0, tk.END)
            self.selected_indices = set(range(len(self.files)))
        return "break"  # Prevent default behavior

    def _delete_selected(self, event=None):
        """Delete selected files from list."""
        selection = self.file_listbox.curselection()
        if not selection:
            return
        
        # Remove in reverse order to maintain indices
        for idx in sorted(selection, reverse=True):
            if 0 <= idx < len(self.files):
                del self.files[idx]
        
        self.selected_indices.clear()
        self._refresh_display()
        return "break"

    def _on_listbox_select(self, event=None):
        """Handle listbox selection change."""
        selection = self.file_listbox.curselection()
        self.selected_indices = set(selection)

    def get_selected_files(self) -> List[ConversionFile]:
        """Get currently selected files (or all if none selected)."""
        if self.selected_indices:
            return [self.files[i] for i in sorted(self.selected_indices) if i < len(self.files)]
        return self.files  # Return all if none selected


    def _on_drop(self, event):
        """Handle dropped files using production-grade Unicode parser."""
        try:
            # Use parse_dropped_paths for robust multi-file Unicode support
            file_paths = parse_dropped_paths(self, event.data)
            added = self.add_files(file_paths)
            
            # Success log message
            if added > 0:
                logger.info(f"Drag & drop: Added {added} file(s)")
                # Log to UI using app instance
                if self.app_instance and hasattr(self.app_instance, '_log'):
                    self.app_instance._log(f"✅ Đã thêm {added} file(s) thành công")
        except Exception as e:
            logger.error(f"Drop error: {e}")

    def add_files(self, paths: List[str]) -> int:
        """Add files to the list with success logging."""
        added = 0
        skipped = 0
        try:
            for path in paths:
                # Check extension
                ext = Path(path).suffix.lower()
                if ext not in ALL_EXTENSIONS:
                    skipped += 1
                    continue

                # Check if already exists
                if any(f.path == path for f in self.files):
                    skipped += 1
                    continue

                self.files.append(ConversionFile(path=path))
                added += 1

            if added > 0:
                self._refresh_display()
                # Log success to console
                logger.info(f"Added {added} file(s) successfully" + 
                          (f" (skipped {skipped})" if skipped > 0 else ""))
                
        except Exception as e:
            logger.error(f"Add files error: {e}")

        return added

    def clear(self):
        """Clear all files."""
        try:
            self.files.clear()
            self._refresh_display()
        except Exception as e:
            logger.error(f"Clear error: {e}")

    def remove_completed(self):
        """Remove completed files."""
        try:
            self.files = [f for f in self.files if f.status != "completed"]
            self._refresh_display()
        except Exception as e:
            logger.error(f"Remove completed error: {e}")

    def _refresh_display(self):
        """Refresh the file list display with debouncing for large lists."""
        try:
            # Debounce: cancel previous scheduled refresh
            if hasattr(self, '_refresh_job') and self._refresh_job:
                self.after_cancel(self._refresh_job)
            
            # Schedule refresh after 50ms debounce
            self._refresh_job = self.after(50, self._do_refresh_display)
        except Exception as e:
            logger.error(f"Refresh display error: {e}")

    def _do_refresh_display(self):
        """Actual refresh implementation."""
        try:
            count = len(self.files)

            # Update type bar
            self._update_type_bar()

            # Update count
            self.count_label.configure(text=f"{count} file{'s' if count != 1 else ''}")

            # Update type breakdown
            type_counts = {ft: 0 for ft in FileType}
            for f in self.files:
                type_counts[f.file_type] += 1

            parts = []
            if type_counts[FileType.EXCEL]: parts.append(f"📗{type_counts[FileType.EXCEL]}")
            if type_counts[FileType.WORD]: parts.append(f"📘{type_counts[FileType.WORD]}")
            if type_counts[FileType.POWERPOINT]: parts.append(f"📙{type_counts[FileType.POWERPOINT]}")
            self.types_label.configure(text=" ".join(parts))

            # Update list display
            if count == 0:
                self.file_listbox.pack_forget()
                self.drop_label.pack(expand=True, pady=30)
            else:
                self.drop_label.pack_forget()
                self.file_listbox.pack(fill="both", expand=True)

                # Clear and repopulate listbox
                self.file_listbox.delete(0, tk.END)

                # Progressive rendering: show only first 200 files for performance
                MAX_DISPLAY = 200
                display_files = self.files[:MAX_DISPLAY]
                
                for i, f in enumerate(display_files, 1):
                    status_icon = {
                        "pending": f.icon,
                        "converting": "⏳",
                        "completed": "✅",
                        "failed": "❌"
                    }.get(f.status, f.icon)
                    self.file_listbox.insert(tk.END, f"{status_icon} {i:3d}. {f.filename}")
                
                # Add "more files" indicator if truncated
                if count > MAX_DISPLAY:
                    self.file_listbox.insert(tk.END, f"... và {count - MAX_DISPLAY} files nữa")

            # Callback
            if self.on_selection_change:
                self.on_selection_change(self.files)
        except Exception as e:
            logger.error(f"Refresh display error: {e}")

    def _update_type_bar(self):
        """Update the file type distribution bar."""
        try:
            if not self.files:
                self.excel_bar.place_forget()
                self.word_bar.place_forget()
                self.ppt_bar.place_forget()
                return

            type_counts = {ft: 0 for ft in FileType}
            for f in self.files:
                type_counts[f.file_type] += 1

            total = len(self.files)
            x = 0

            for ftype, bar in [(FileType.EXCEL, self.excel_bar),
                               (FileType.WORD, self.word_bar),
                               (FileType.POWERPOINT, self.ppt_bar)]:
                if type_counts[ftype]:
                    width = type_counts[ftype] / total
                    bar.place(relx=x, rely=0, relwidth=width, relheight=1)
                    x += width
                else:
                    bar.place_forget()
        except Exception as e:
            logger.error(f"Update type bar error: {e}")


# ============================================================================
# MAIN APPLICATION
# ============================================================================

class ConverterProApp(TkDnDWrapper):
    """Professional-grade Office to PDF Converter with robust Unicode drag-and-drop support."""

    VERSION = "4.2.91"

    def __init__(self):
        super().__init__()

        # Core components
        self.config = Config()
        self.db = RecentFilesDB()
        self.engine: Optional[ConversionEngine] = None

        # State
        self.is_converting = False
        self.output_folder = self.config.get("output_folder", "")
        self.conversion_start_time = 0.0

        # UI references (will be set in _create_layout)
        self.file_panel: Optional[FileListPanel] = None
        self.btn_convert: Optional[ctk.CTkButton] = None
        self.progress_frame: Optional[ctk.CTkFrame] = None
        self.progress_bar: Optional[ctk.CTkProgressBar] = None
        self.progress_label: Optional[ctk.CTkLabel] = None
        self.progress_percent: Optional[ctk.CTkLabel] = None
        self.progress_title: Optional[ctk.CTkLabel] = None
        self.status_badge: Optional[ctk.CTkLabel] = None
        self.elapsed_label: Optional[ctk.CTkLabel] = None
        self.remaining_label: Optional[ctk.CTkLabel] = None
        self.estimated_label: Optional[ctk.CTkLabel] = None
        self.current_file_label: Optional[ctk.CTkLabel] = None
        self.btn_stop: Optional[ctk.CTkButton] = None
        self.log_textbox: Optional[ctk.CTkTextbox] = None
        self.output_label: Optional[ctk.CTkLabel] = None
        self.password_entry: Optional[ctk.CTkEntry] = None
        self.theme_switch: Optional[ctk.CTkSwitch] = None
        self.main_content_frame: Optional[ctk.CTkFrame] = None

        # Time tracking
        self.total_estimated_time: float = 0.0
        # Variables - Load from config
        self.var_quality = ctk.IntVar(value=self.config.get("pdf_quality", 0))
        self.var_dpi = ctk.StringVar(value=str(self.config.get("pdf_dpi", "300")))
        self.var_scan_mode = ctk.BooleanVar(value=self.config.get("scan_mode", False))
        self.var_password = ctk.StringVar()
        self.var_password_enabled = ctk.BooleanVar(value=False)
        self.var_page_range = ctk.StringVar(value=self.config.get("page_range", ""))
        self.var_sheet_option = ctk.IntVar(value=self.config.get("sheet_option", 0))
        self.var_sheet_index = ctk.StringVar(value=self.config.get("sheet_index", "1"))
        self.var_output_same = ctk.BooleanVar(value=self.config.get("output_same", True))
        self.var_output_folder = ctk.StringVar(value=self.config.get("output_folder", ""))
        # Setup window
        self.title(f"Office to PDF Converter Pro - v{self.VERSION} | Tung Do - 0914665866")
        self.geometry("1000x750")
        self.minsize(900, 700)

        # Center window
        self._center_window()

        # Build UI
        self._create_layout()

        # Keyboard shortcuts
        self._setup_shortcuts()

        # Setup drag and drop
        self._setup_drag_drop()

        # Fix for window restore after minimize (windnd compatibility)
        self.bind('<Map>', self._on_window_restore)
        
        # Cleanup
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Initial log
        self._log(f"🚀 Office to PDF Converter Pro v{self.VERSION}")
        if fitz:
            self._log("📄 PyMuPDF: Hỗ trợ xử lý trang PDF")
        else:
            self._log("⚠️ PyMuPDF không có: Không hỗ trợ chọn trang")
        if HAS_TKDND:
            self._log("📁 Drag & Drop: Kéo thả file hoạt động (TkinterDnD2)")

        # Cleanup old temp files from previous sessions
        self._cleanup_temp_files()

        # Check for updates on startup
        self._check_for_updates()

    def _cleanup_temp_files(self):
        """Clean up orphaned temp files from crashed conversions."""
        try:
            import glob
            temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
            patterns = ["tmp_*.xlsx", "tmp_*.xls", "tmp_*.docx", "tmp_*.doc", 
                       "tmp_*.pptx", "tmp_*.ppt", "tmp_*.pdf"]
            
            cleaned = 0
            for pattern in patterns:
                for f in glob.glob(os.path.join(temp_dir, pattern)):
                    try:
                        # Only delete files older than 1 hour
                        if os.path.getmtime(f) < (time.time() - 3600):
                            os.remove(f)
                            cleaned += 1
                    except (OSError, PermissionError):
                        pass  # File in use, skip
            
            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} orphaned temp files")
        except Exception as e:
            logger.debug(f"Temp cleanup error: {e}")

    def _check_for_updates(self):
        """Check for updates asynchronously."""
        try:
            from office_converter.utils.updater import check_for_updates_on_startup
            self.after(2000, lambda: check_for_updates_on_startup(self))
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Update check error: {e}")

    def _center_window(self):
        """Center window on screen."""
        try:
            self.update_idletasks()
            w, h = 1000, 750
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception as e:
            logger.error(f"Center window error: {e}")

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        try:
            self.bind('<Control-o>', lambda e: self._add_files())
            self.bind('<Control-v>', lambda e: self._paste_files())
            self.bind('<Delete>', lambda e: self._clear_files())
            self.bind('<Return>', lambda e: self._start_conversion())
            self.bind('<Escape>', lambda e: self._stop_conversion())
            self.bind('<F1>', lambda e: self._show_shortcuts())
        except Exception as e:
            logger.error(f"Setup shortcuts error: {e}")

    def _setup_drag_drop(self):
        """Setup drag and drop support using TkinterDnD2 with Unicode support."""
        if not HAS_TKDND:
            logger.info("tkinterdnd2 not available, drag drop disabled")
            return

        try:
            # Register the main window for file drops
            self.drop_target_register(DND_FILES)
            # Bind drop event
            self.dnd_bind('<<Drop>>', self._handle_drop)
            logger.info("Drag and drop enabled with Unicode support")
        except Exception as e:
            logger.error(f"Setup drag drop error: {e}")

    def _handle_drop(self, event):
        """Handle dropped files with robust Unicode path parsing via tk.splitlist()."""
        try:
            if not event.data:
                return

            # Parse paths using production-grade utility that handles
            # Tcl list format with tk.splitlist() for perfect Unicode support
            file_paths = parse_dropped_paths(self, event.data)
            
            if not file_paths:
                logger.warning("No valid files in drop event")
                return

            # Get all supported extensions
            all_extensions = set()
            for ext_set in FILE_EXTENSIONS.values():
                all_extensions.update(ext_set)

            added_count = 0
            for file_path in file_paths:
                try:
                    # Check extension
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in all_extensions:
                        # Add to file panel
                        if self.file_panel:
                            conv_file = ConversionFile(path=file_path)
                            if conv_file not in self.file_panel.files:
                                self.file_panel.files.append(conv_file)
                                added_count += 1
                    else:
                        # Unsupported extension
                        basename = os.path.basename(file_path)
                        self._log(f"⚠️ File không hỗ trợ: {basename}")
                except Exception as file_err:
                    logger.warning(f"Skip file due to error: {file_err}")
                    continue

            if added_count > 0:
                # Refresh display
                if self.file_panel:
                    self.file_panel._refresh_display()
                self._log(f"📁 Thả thêm {added_count} file(s)")
                self._on_files_changed(self.file_panel.files if self.file_panel else [])
                
        except Exception as e:
            logger.error(f"Handle drop error: {e}")
            self._log(f"❌ Lỗi kéo thả: {e}")

    def _create_layout(self):
        """Create the main layout."""
        try:
            # === HEADER ===
            self._create_header()

            # === MAIN CONTENT ===
            self.main_content_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.main_content_frame.pack(fill="both", expand=True, padx=15, pady=10)

            # Left column: File list
            left_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=12)
            left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

            self.file_panel = FileListPanel(
                left_frame,
                on_selection_change=self._on_files_changed,
                app_instance=self  # Pass app reference for logging
            )
            self.file_panel.pack(fill="both", expand=True)

            # File action buttons
            file_btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
            file_btn_frame.pack(fill="x", padx=10, pady=10)

            ctk.CTkButton(file_btn_frame, text="➕ Files", width=80,
                         command=self._add_files).pack(side="left", padx=2)
            ctk.CTkButton(file_btn_frame, text="📁 Folder", width=80,
                         command=self._add_folder,
                         fg_color="transparent", border_width=2).pack(side="left", padx=2)
            ctk.CTkButton(file_btn_frame, text="🔧 PDF Tools", width=90,
                         command=self._open_pdf_tools,
                         fg_color="#3B82F6", hover_color="#2563EB").pack(side="left", padx=2)
            ctk.CTkButton(file_btn_frame, text="📊 Excel Tools", width=95,
                         command=self._open_excel_tools,
                         fg_color="#10B981", hover_color="#059669").pack(side="left", padx=2)
            ctk.CTkButton(file_btn_frame, text="🗑️", width=40,
                         command=self._clear_files,
                         fg_color="transparent", border_width=2,
                         hover_color="#DC2626").pack(side="right")

            # Right column: Options
            right_frame = ctk.CTkFrame(self.main_content_frame, width=320, corner_radius=12)
            right_frame.pack(side="right", fill="y", padx=(5, 0))
            right_frame.pack_propagate(False)

            # Options panel - takes full height of right column
            self._create_options_panel(right_frame)

            # === CONVERT BUTTON ===
            self.btn_convert = ctk.CTkButton(
                self.main_content_frame,
                text="🚀 CHUYỂN ĐỔI SANG PDF",
                command=self._start_conversion,
                height=50,
                font=ctk.CTkFont(size=18, weight="bold"),
                fg_color="#16A34A",
                hover_color="#15803D",
                state="disabled"
            )
            self.btn_convert.pack(fill="x", pady=(10, 0))

            # === PROGRESS PANEL (initially hidden) ===
            self.progress_frame = ctk.CTkFrame(
                self.main_content_frame,
                corner_radius=15,
                border_width=2,
                border_color="#374151"
            )

            # ─── HEADER: Title + Status ───
            header_frame = ctk.CTkFrame(self.progress_frame, fg_color="#1F2937", corner_radius=10)
            header_frame.pack(fill="x", padx=15, pady=(15, 10))

            header_inner = ctk.CTkFrame(header_frame, fg_color="transparent")
            header_inner.pack(fill="x", padx=15, pady=12)

            # Icon + Title
            title_frame = ctk.CTkFrame(header_inner, fg_color="transparent")
            title_frame.pack(side="left")

            ctk.CTkLabel(
                title_frame,
                text="⏳",
                font=ctk.CTkFont(size=24)
            ).pack(side="left", padx=(0, 10))

            self.progress_title = ctk.CTkLabel(
                title_frame,
                text="Đang chuyển đổi...",
                font=ctk.CTkFont(size=16, weight="bold")
            )
            self.progress_title.pack(side="left")

            # Status badge
            self.status_badge = ctk.CTkLabel(
                header_inner,
                text="ĐANG XỬ LÝ",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#3B82F6",
                corner_radius=5,
                padx=10,
                pady=3
            )
            self.status_badge.pack(side="right")

            # ─── MAIN: Big Percent + Progress Bar ───
            main_section = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
            main_section.pack(fill="x", padx=20, pady=10)

            # Large centered percentage
            percent_frame = ctk.CTkFrame(main_section, fg_color="transparent")
            percent_frame.pack(fill="x", pady=(0, 10))

            self.progress_percent = ctk.CTkLabel(
                percent_frame,
                text="0%",
                font=ctk.CTkFont(size=48, weight="bold"),
                text_color="#22C55E"
            )
            self.progress_percent.pack()

            self.progress_label = ctk.CTkLabel(
                percent_frame,
                text="Đang xử lý 0/0 files",
                font=ctk.CTkFont(size=13),
                text_color="#9CA3AF"
            )
            self.progress_label.pack()

            # Progress bar with glow effect
            progress_container = ctk.CTkFrame(main_section, fg_color="#1F2937", corner_radius=8)
            progress_container.pack(fill="x", pady=5)

            self.progress_bar = ctk.CTkProgressBar(
                progress_container,
                height=12,
                corner_radius=6,
                progress_color="#22C55E",
                fg_color="#374151"
            )
            self.progress_bar.pack(fill="x", padx=8, pady=8)
            self.progress_bar.set(0)

            # ─── TIME CARDS: Elapsed | Estimated | Remaining ───
            time_cards = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
            time_cards.pack(fill="x", padx=15, pady=10)

            # Configure grid columns
            time_cards.grid_columnconfigure(0, weight=1)
            time_cards.grid_columnconfigure(1, weight=1)
            time_cards.grid_columnconfigure(2, weight=1)

            # Elapsed time card
            elapsed_card = ctk.CTkFrame(time_cards, fg_color="#1F2937", corner_radius=8)
            elapsed_card.grid(row=0, column=0, padx=5, sticky="ew")

            ctk.CTkLabel(
                elapsed_card,
                text="⏱️ Đã chạy",
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF"
            ).pack(pady=(8, 2))

            self.elapsed_label = ctk.CTkLabel(
                elapsed_card,
                text="00:00",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color="#60A5FA"
            )
            self.elapsed_label.pack(pady=(0, 8))

            # Estimated time card
            est_card = ctk.CTkFrame(time_cards, fg_color="#1F2937", corner_radius=8)
            est_card.grid(row=0, column=1, padx=5, sticky="ew")

            ctk.CTkLabel(
                est_card,
                text="📊 Ước tính",
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF"
            ).pack(pady=(8, 2))

            self.estimated_label = ctk.CTkLabel(
                est_card,
                text="--:--",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color="#FBBF24"
            )
            self.estimated_label.pack(pady=(0, 8))

            # Remaining time card
            remaining_card = ctk.CTkFrame(time_cards, fg_color="#1F2937", corner_radius=8)
            remaining_card.grid(row=0, column=2, padx=5, sticky="ew")

            ctk.CTkLabel(
                remaining_card,
                text="⏳ Còn lại",
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF"
            ).pack(pady=(8, 2))

            self.remaining_label = ctk.CTkLabel(
                remaining_card,
                text="--:--",
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color="#F472B6"
            )
            self.remaining_label.pack(pady=(0, 8))

            # ─── CURRENT FILE ───
            file_section = ctk.CTkFrame(self.progress_frame, fg_color="#1F2937", corner_radius=8)
            file_section.pack(fill="x", padx=15, pady=(5, 10))

            file_inner = ctk.CTkFrame(file_section, fg_color="transparent")
            file_inner.pack(fill="x", padx=12, pady=10)

            ctk.CTkLabel(
                file_inner,
                text="📄",
                font=ctk.CTkFont(size=16)
            ).pack(side="left", padx=(0, 8))

            self.current_file_label = ctk.CTkLabel(
                file_inner,
                text="Đang chờ...",
                font=ctk.CTkFont(size=12),
                text_color="#D1D5DB",
                anchor="w"
            )
            self.current_file_label.pack(side="left", fill="x", expand=True)

            # ─── STOP BUTTON ───
            self.btn_stop = ctk.CTkButton(
                self.progress_frame,
                text="⏹️  DỪNG CHUYỂN ĐỔI",
                command=self._stop_conversion,
                font=ctk.CTkFont(size=14, weight="bold"),
                fg_color="#DC2626",
                hover_color="#B91C1C",
                height=45,
                corner_radius=8
            )
            self.btn_stop.pack(fill="x", padx=15, pady=(5, 15))

            # === LOG ===
            log_frame = ctk.CTkFrame(self, corner_radius=12)
            log_frame.pack(fill="x", padx=15, pady=(5, 15))

            log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
            log_header.pack(fill="x", padx=10, pady=(10, 5))

            ctk.CTkLabel(log_header, text="📋 Log",
                        font=ctk.CTkFont(weight="bold")).pack(side="left")

            # Language selector
            lang_frame = ctk.CTkFrame(log_header, fg_color="transparent")
            lang_frame.pack(side="right", padx=10)

            ctk.CTkLabel(lang_frame, text="🌐",
                        font=ctk.CTkFont(size=14)).pack(side="left", padx=(0, 5))

            # Get language names for dropdown
            from office_converter.utils.localization import get_language_names
            lang_names = get_language_names()
            current_lang = self.config.get("language", "vi")
            current_lang_name = lang_names.get(current_lang, "Tiếng Việt")

            self.lang_dropdown = ctk.CTkComboBox(
                lang_frame,
                values=list(lang_names.values()),
                width=100,
                state="readonly",
                command=self._change_language
            )
            self.lang_dropdown.set(current_lang_name)
            self.lang_dropdown.pack(side="left")

            ctk.CTkButton(log_header, text="🛠️ PDF Tools", width=100,
                         command=self._open_pdf_tools).pack(side="right", padx=5)
            
            ctk.CTkButton(log_header, text="📂 File Tools", width=100,
                         command=self._open_file_tools).pack(side="right", padx=5)

            self.log_textbox = ctk.CTkTextbox(log_frame, height=80,
                                              font=ctk.CTkFont(family="Consolas", size=11))
            self.log_textbox.pack(fill="x", padx=10, pady=(0, 10))

        except Exception as e:
            logger.error(f"Create layout error: {e}")
            messagebox.showerror("Lỗi", f"Không thể tạo giao diện: {e}")

    def _create_header(self):
        """Create header with title and controls."""
        try:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=(15, 5))

            # Title
            title_frame = ctk.CTkFrame(header, fg_color="transparent")
            title_frame.pack(side="left")

            ctk.CTkLabel(title_frame, text="📄 Office to PDF Converter Pro",
                        font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
            ctk.CTkLabel(title_frame, text=f"v{self.VERSION}",
                        text_color="gray").pack(side="left", padx=10)
            # Author info
            ctk.CTkLabel(title_frame, text="| Tung Do - 0914665866",
                        text_color="#4da6ff", font=ctk.CTkFont(size=12)).pack(side="left", padx=5)

            # Controls
            controls = ctk.CTkFrame(header, fg_color="transparent")
            controls.pack(side="right")

            ctk.CTkButton(controls, text="📊", width=35,
                         command=self._show_stats,
                         fg_color="transparent", border_width=1).pack(side="left", padx=2)
            ctk.CTkButton(controls, text="⚙️", width=35,
                         command=self._show_settings,
                         fg_color="transparent", border_width=1).pack(side="left", padx=2)
            ctk.CTkButton(controls, text="❓", width=35,
                         command=self._show_shortcuts,
                         fg_color="transparent", border_width=1).pack(side="left", padx=2)

            # Theme switch
            self.theme_switch = ctk.CTkSwitch(controls, text="🌙",
                                              command=self._toggle_theme)
            self.theme_switch.pack(side="left", padx=(15, 0))
            if ctk.get_appearance_mode() == "Dark":
                self.theme_switch.select()
        except Exception as e:
            logger.error(f"Create header error: {e}")

    def _create_options_panel(self, parent):
        """Create options panel."""
        try:
            options = ctk.CTkFrame(parent, fg_color="transparent")
            options.pack(fill="x", padx=10, pady=5)

            # Output folder
            output_frame = ctk.CTkFrame(options, fg_color="transparent")
            output_frame.pack(fill="x", pady=5)

            ctk.CTkLabel(output_frame, text="📂 Output:").pack(side="left")
            # Show saved output folder or default
            saved_folder = self.config.get("output_folder", "")
            if saved_folder and os.path.exists(saved_folder):
                self.output_folder = saved_folder
                output_text = os.path.basename(saved_folder)
            else:
                output_text = "Cùng folder gốc"
            self.output_label = ctk.CTkLabel(output_frame, text=output_text,
                                              text_color="gray" if not saved_folder else "#22C55E",
                                              wraplength=150)
            self.output_label.pack(side="left", padx=5)
            ctk.CTkButton(output_frame, text="Đổi", width=50, height=25,
                         command=self._select_output,
                         fg_color="transparent", border_width=1).pack(side="right")

            # Quality
            quality_frame = ctk.CTkFrame(options, fg_color="transparent")
            quality_frame.pack(fill="x", pady=5)

            ctk.CTkLabel(quality_frame, text="📊 Chất lượng:").pack(side="left")
            ctk.CTkRadioButton(quality_frame, text="Cao", variable=self.var_quality,
                              value=0, command=self._on_quality_change, width=60).pack(side="left", padx=2)
            ctk.CTkRadioButton(quality_frame, text="Nhỏ", variable=self.var_quality,
                              value=1, command=self._on_quality_change, width=60).pack(side="left", padx=2)
            ctk.CTkRadioButton(quality_frame, text="DPI:", variable=self.var_quality,
                              value=2, command=self._on_quality_change, width=55).pack(side="left", padx=2)

            self.dpi_frame = ctk.CTkFrame(quality_frame, fg_color="transparent")
            self.dpi_frame.pack(side="left")

            self.dpi_entry = ctk.CTkEntry(self.dpi_frame, width=45, textvariable=self.var_dpi)
            self.dpi_entry.pack(side="left")
            
            # Initial state
            self._on_quality_change()

            # Scan mode
            ctk.CTkSwitch(options, text="📷 Scan Mode",
                         variable=self.var_scan_mode,
                         command=self._save_scan_mode).pack(fill="x", pady=5)

            # Password
            pw_frame = ctk.CTkFrame(options, fg_color="transparent")
            pw_frame.pack(fill="x", pady=5)

            ctk.CTkSwitch(pw_frame, text="🔒", variable=self.var_password_enabled,
                         command=self._on_password_toggle).pack(side="left")
            self.password_entry = ctk.CTkEntry(pw_frame, textvariable=self.var_password,
                                               show="*", width=120, state="disabled",
                                               placeholder_text="Mật khẩu")
            self.password_entry.pack(side="left", padx=5)

            # Excel sheet selection
            sheet_frame = ctk.CTkFrame(options, fg_color="transparent")
            sheet_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(sheet_frame, text="📗 Sheet (Excel):").pack(side="left")
            sheet_entry = ctk.CTkEntry(sheet_frame, textvariable=self.var_sheet_index,
                        width=80, placeholder_text="all")
            sheet_entry.pack(side="left", padx=5)
            ctk.CTkLabel(sheet_frame, text="1-3, 5 hoặc trống=tất cả", 
                        text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left")

            # Excel page range (renamed from PDF)
            page_frame = ctk.CTkFrame(options, fg_color="transparent")
            page_frame.pack(fill="x", pady=5)

            ctk.CTkLabel(page_frame, text="📄 Trang Excel:").pack(side="left")
            page_entry = ctk.CTkEntry(page_frame, textvariable=self.var_page_range,
                        width=80, placeholder_text="all")
            page_entry.pack(side="left", padx=5)
            ctk.CTkLabel(page_frame, text="Chỉ xuất các trang chỉ định", 
                        text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left")
            # Save page range on focus out
            page_entry.bind("<FocusOut>", lambda e: self._save_page_range())
        except Exception as e:
            logger.error(f"Create options error: {e}")

    def _on_quality_change(self):
        """Handle quality selection change."""
        try:
            val = self.var_quality.get()
            if val == 2:
                self.dpi_entry.configure(state="normal")
            else:
                self.dpi_entry.configure(state="disabled")
            self._save_quality()
        except Exception:
            pass

    def _save_quality(self):
        """Save quality setting to config."""
        try:
            self.config.set("pdf_quality", self.var_quality.get())
            if self.var_quality.get() == 2:
                self.config.set("pdf_dpi", self.var_dpi.get())
            self.config.save()
        except Exception as e:
            logger.error(f"Save quality error: {e}")

    def _save_scan_mode(self):
        """Save scan mode setting to config."""
        try:
            self.config.set("scan_mode", self.var_scan_mode.get())
            self.config.save()
        except Exception as e:
            logger.error(f"Save scan mode error: {e}")

    def _save_page_range(self):
        """Save page range setting to config."""
        try:
            self.config.set("page_range", self.var_page_range.get())
            self.config.save()
        except Exception as e:
            logger.error(f"Save page range error: {e}")

    # =========== EVENT HANDLERS ===========

    def _on_files_changed(self, files: List[ConversionFile]):
        """Called when file list changes."""
        try:
            has_files = len(files) > 0
            if self.btn_convert:
                self.btn_convert.configure(state="normal" if has_files else "disabled")
        except Exception as e:
            logger.error(f"On files changed error: {e}")

    def _on_password_toggle(self):
        """Toggle password entry state."""
        try:
            if self.password_entry:
                if self.var_password_enabled.get():
                    self.password_entry.configure(state="normal")
                else:
                    self.password_entry.configure(state="disabled")
        except Exception as e:
            logger.error(f"Password toggle error: {e}")

    def _toggle_theme(self):
        """Toggle dark/light theme."""
        try:
            if self.theme_switch:
                mode = "dark" if self.theme_switch.get() else "light"
                ctk.set_appearance_mode(mode)
        except Exception as e:
            logger.error(f"Toggle theme error: {e}")

    # =========== FILE ACTIONS ===========

    def _add_files(self):
        """Add files via dialog."""
        try:
            filetypes = [
                ("Office Files", " ".join(f"*{ext}" for ext in ALL_EXTENSIONS)),
                ("Excel", "*.xlsx *.xls *.xlsm *.xlsb"),
                ("Word", "*.docx *.doc"),
                ("PowerPoint", "*.pptx *.ppt"),
            ]
            files = filedialog.askopenfilenames(filetypes=filetypes)
            if files and self.file_panel:
                added = self.file_panel.add_files(list(files))
                if added:
                    self._log(f"➕ Đã thêm {added} file(s)")
        except Exception as e:
            logger.error(f"Add files error: {e}")
            messagebox.showerror("Lỗi", f"Không thể thêm files: {e}")

    def _add_folder(self):
        """Add files from folder."""
        try:
            folder = filedialog.askdirectory()
            if folder and self.file_panel:
                files = []
                for f in os.listdir(folder):
                    ext = Path(f).suffix.lower()
                    if ext in ALL_EXTENSIONS:
                        files.append(os.path.join(folder, f))

                if files:
                    added = self.file_panel.add_files(files)
                    self._log(f"📁 Đã thêm {added} file(s) từ folder")
        except Exception as e:
            logger.error(f"Add folder error: {e}")
            messagebox.showerror("Lỗi", f"Không thể thêm folder: {e}")

    def _show_recent(self):
        """Show recent files dialog."""
        try:
            recent = self.db.get_recent(10)

            if not recent:
                messagebox.showinfo("Recent Files", "Chưa có files gần đây")
                return

            dialog = ctk.CTkToplevel(self)
            dialog.title("🕐 Recent Files")
            dialog.geometry("500x400")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="📋 Files gần đây",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=15)

            listbox_frame = ctk.CTkFrame(dialog)
            listbox_frame.pack(fill="both", expand=True, padx=20, pady=10)

            textbox = ctk.CTkTextbox(listbox_frame, font=ctk.CTkFont(size=12))
            textbox.pack(fill="both", expand=True)

            for i, path in enumerate(recent, 1):
                textbox.insert("end", f"{i}. {Path(path).name}\n")
            textbox.configure(state="disabled")

            def add_all():
                if self.file_panel:
                    self.file_panel.add_files(recent)
                dialog.destroy()
                self._log(f"➕ Đã thêm {len(recent)} file(s) từ recent")

            ctk.CTkButton(dialog, text="➕ Thêm tất cả",
                         command=add_all).pack(pady=15)
        except Exception as e:
            logger.error(f"Show recent error: {e}")
            messagebox.showerror("Lỗi", f"Không thể hiển thị recent files: {e}")

    def _paste_files(self):
        """Paste files from clipboard."""
        # Future: implement clipboard paste
        pass

    def _change_language(self, selected_name: str):
        """Change application language."""
        try:
            from office_converter.utils.localization import get_language_names, set_language

            # Find language code from name
            lang_names = get_language_names()
            lang_code = None
            for code, name in lang_names.items():
                if name == selected_name:
                    lang_code = code
                    break

            if lang_code:
                # Save to config
                self.config.set("language", lang_code)
                self.config.save()
                set_language(lang_code)

                # Notify user to restart
                self._log(f"🌐 Ngôn ngữ: {selected_name}")

                # Show restart dialog
                result = messagebox.askyesno(
                    "Restart Required / Cần khởi động lại",
                    f"Đã chuyển sang {selected_name}.\n"
                    f"Changed to {selected_name}.\n\n"
                    "Khởi động lại ứng dụng để áp dụng?\n"
                    "Restart application to apply?"
                )
                if result:
                    self.destroy()
                    import sys
                    import subprocess
                    subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            logger.error(f"Change language error: {e}")

    def _open_pdf_tools(self):
        """Open PDF Tools Pro dialog."""
        try:
            from office_converter.ui.pdf_tools_pro import PDFToolsDialogPro
            PDFToolsDialogPro(self, "vi")
        except Exception as e:
            logger.error(f"Open PDF Tools error: {e}")
            messagebox.showerror("Lỗi", f"Không thể mở PDF Tools: {e}")

    def _open_excel_tools(self):
        """Open Excel Tools dialog."""
        try:
            from office_converter.ui.excel_tools_ui import ExcelToolsDialog
            ExcelToolsDialog(self, "vi")
        except ImportError as e:
            logger.error(f"Excel Tools import error: {e}")
            messagebox.showerror(
                "Thiếu thư viện",
                "Cần cài đặt openpyxl để sử dụng Excel Tools.\n\n"
                "Chạy lệnh: pip install openpyxl"
            )
        except Exception as e:
            logger.error(f"Open Excel Tools error: {e}")
            messagebox.showerror("Lỗi", f"Không thể mở Excel Tools: {e}")

    def _clear_files(self):
        """Clear file list."""
        try:
            if self.file_panel and self.file_panel.files:
                self.file_panel.clear()
                if self.preview_panel:
                    self.preview_panel.clear()
                self._log("🗑️ Đã xóa danh sách")
        except Exception as e:
            logger.error(f"Clear files error: {e}")

    def _select_output(self):
        """Select output folder."""
        try:
            folder = filedialog.askdirectory()
            if folder:
                self.output_folder = folder
                display = Path(folder).name
                if self.output_label:
                    self.output_label.configure(text=display, text_color="#22C55E")
                self.config.set("output_folder", folder)
        except Exception as e:
            logger.error(f"Select output error: {e}")

    # =========== CONVERSION ===========

    def _start_conversion(self):
        """Start conversion process."""
        try:
            if not self.file_panel or not self.file_panel.files or self.is_converting:
                return

            self.is_converting = True
            self.conversion_start_time = time.time()

            # Calculate estimated time - MOVED TO BACKGROUND
            # self.total_estimated_time = self._calculate_estimated_time()
            # Default estimate (5s per file) prevents determining size on main thread
            self.total_estimated_time = len(self.file_panel.files) * 5.0

            # UI updates
            if self.btn_convert:
                self.btn_convert.configure(state="disabled", text="⏳ Đang chuyển đổi...")

            # Reset progress UI
            if self.progress_bar:
                self.progress_bar.set(0)
            if self.progress_percent:
                self.progress_percent.configure(text="0%", text_color="#22C55E")
            if self.progress_label:
                total = len(self.file_panel.files)
                self.progress_label.configure(text=f"Đang xử lý 0/{total} files")
            if self.progress_title:
                self.progress_title.configure(text="Đang chuyển đổi...")
            if self.status_badge:
                self.status_badge.configure(text="ĐANG XỬ LÝ", fg_color="#3B82F6")
            if self.elapsed_label:
                self.elapsed_label.configure(text="00:00")
            if self.remaining_label:
                est_mins, est_secs = divmod(int(self.total_estimated_time), 60)
                self.remaining_label.configure(text=f"{est_mins:02d}:{est_secs:02d}")
            if self.estimated_label:
                est_mins, est_secs = divmod(int(self.total_estimated_time), 60)
                self.estimated_label.configure(text=f"{est_mins:02d}:{est_secs:02d}")
            if self.current_file_label:
                self.current_file_label.configure(text="Đang chờ...")

            # Show progress frame
            if self.progress_frame and self.btn_convert:
                self.progress_frame.pack(fill="x", pady=15, after=self.btn_convert)

            # Parse DPI
            try:
                dpi = int(self.var_dpi.get())
            except (ValueError, TypeError):
                dpi = 300

            # Create options
            options = ConversionOptions(
                quality=self.var_quality.get(),
                quality_dpi=dpi,
                scan_mode=self.var_scan_mode.get(),
                password=self.var_password.get() if self.var_password_enabled.get() else None,
                page_range=self.var_page_range.get() or None,
            )

            if self.var_sheet_option.get() == 1:
                parsed = parse_page_range(self.var_sheet_index.get())
                if parsed:
                    options.sheet_indices = [i + 1 for i in parsed]

            # Create engine with callbacks
            self.engine = ConversionEngine(
                on_progress=self._on_progress,
                on_file_complete=self._on_file_complete,
                on_error=self._on_error
            )

            # Start time display
            self._update_time_display()
        
            # Force UI update to prevent freeze before thread starts
            self.update_idletasks()
        
            # Start conversion thread
            thread = threading.Thread(
                target=self._run_conversion,
                args=(options,),
                daemon=True
            )
            thread.start()
        except Exception as e:
            self.is_converting = False
            logger.error(f"Start conversion error: {e}")
            messagebox.showerror("Lỗi", f"Không thể bắt đầu chuyển đổi: {e}")

    def _calculate_estimated_time(self) -> float:
        """Calculate total estimated conversion time."""
        try:
            from office_converter.utils.progress_estimator import estimate_conversion_time
            total = 0.0
            if self.file_panel:
                for f in self.file_panel.files:
                    try:
                        total += estimate_conversion_time(f.path)
                    except Exception:
                        total += 10.0  # Default 10 seconds
            return total
        except ImportError:
            # Fallback: 10 seconds per file
            return len(self.file_panel.files) * 10.0 if self.file_panel else 0.0

    def _run_conversion(self, options: ConversionOptions):
        """Run conversion in background thread."""
        try:
            if self.engine and self.file_panel:
                self.engine.convert_batch(
                    self.file_panel.files,
                    options,
                    self.output_folder if self.output_folder else None
                )
        except Exception as e:
            logger.error(f"Run conversion error: {e}")
        finally:
            self.after(0, self._on_conversion_done)

    def _stop_conversion(self):
        """Stop conversion immediately (force stop)."""
        try:
            if self.engine:
                self._log("⏹️ Đang dừng ngay lập tức...")
                
                # Force stop - kills Office processes if needed
                self.engine.stop(force=True)
                
                # Immediately update UI
                self.is_converting = False
                
                # Hide progress frame
                if hasattr(self, 'progress_frame') and self.progress_frame:
                    self.progress_frame.pack_forget()
                
                # Re-enable convert button and show main content
                if hasattr(self, 'btn_convert') and self.btn_convert:
                    self.btn_convert.configure(state="normal")
                if hasattr(self, 'main_content_frame') and self.main_content_frame:
                    self.main_content_frame.pack(fill="both", expand=True, padx=15, pady=10)
                
                self._log("⏹️ Đã dừng chuyển đổi!")
                
                # Mark pending files as cancelled
                if self.file_panel:
                    for f in self.file_panel.files:
                        if f.status == "converting" or f.status == "pending":
                            f.status = "pending"  # Reset to pending
                    self.file_panel._refresh_display()
                    
        except Exception as e:
            logger.error(f"Stop conversion error: {e}")

    def _on_progress(self, current: int, total: int, filename: str):
        """Progress callback from engine."""
        try:
            progress = (current + 1) / total
            self.after(0, lambda: self._update_progress_ui(progress, current, total, filename))
        except Exception as e:
            logger.error(f"On progress error: {e}")

    def _update_progress_ui(self, progress: float, current: int, total: int, filename: str):
        """Update progress UI on main thread."""
        try:
            percent = int(progress * 100)

            # Update progress bar with smooth animation
            if self.progress_bar:
                self._animate_progress(progress)

            # Update percent label with color change
            if self.progress_percent:
                # Color changes as progress increases
                if percent < 30:
                    color = "#22C55E"  # Green
                elif percent < 70:
                    color = "#3B82F6"  # Blue
                else:
                    color = "#22C55E"  # Green again for near completion
                self.progress_percent.configure(text=f"{percent}%", text_color=color)

            # Update file count label
            if self.progress_label:
                self.progress_label.configure(text=f"Đang xử lý {current + 1}/{total} files")

            # Update current file name (truncate if too long)
            if self.current_file_label:
                display_name = filename if len(filename) <= 50 else filename[:47] + "..."
                self.current_file_label.configure(text=display_name)

            # Update remaining time estimate based on progress
            if self.remaining_label:
                elapsed = time.time() - self.conversion_start_time
                if progress > 0.05:  # Only calculate after 5% progress
                    estimated_total = elapsed / progress
                    remaining = max(0, estimated_total - elapsed)
                else:
                    remaining = self.total_estimated_time - elapsed

                rem_mins, rem_secs = divmod(int(max(0, remaining)), 60)
                self.remaining_label.configure(text=f"{rem_mins:02d}:{rem_secs:02d}")

        except Exception as e:
            logger.error(f"Update progress UI error: {e}")

    def _animate_progress(self, target: float, steps: int = 5):
        """Smoothly animate progress bar to target value."""
        try:
            current = self.progress_bar.get() if hasattr(self.progress_bar, 'get') else 0
            
            # If target is lower (shouldn't happen) or nearly same, just set directly
            if target <= current or abs(target - current) < 0.01:
                self.progress_bar.set(target)
                return
            
            # Calculate step size
            step_size = (target - current) / steps
            
            def animate_step(step_num):
                if step_num >= steps:
                    self.progress_bar.set(target)
                    return
                
                new_value = current + (step_size * (step_num + 1))
                self.progress_bar.set(min(new_value, target))
                
                # Schedule next step (16ms = ~60fps)
                self.after(16, lambda: animate_step(step_num + 1))
            
            animate_step(0)
        except Exception:
            # Fallback to direct set
            self.progress_bar.set(target)

    def _on_file_complete(self, conv_file: ConversionFile):
        """File completion callback."""
        try:
            if conv_file.status == "completed":
                self.after(0, lambda: self._log(f"✅ {conv_file.filename}"))
            else:
                self.after(0, lambda: self._log(f"❌ {conv_file.filename}"))

            if self.file_panel:
                self.after(0, self.file_panel._refresh_display)
        except Exception as e:
            logger.error(f"On file complete error: {e}")

    def _on_error(self, conv_file: ConversionFile, error: Exception):
        """Error callback."""
        try:
            self.after(0, lambda: self._log(f"❌ {conv_file.filename}: {str(error)[:50]}"))
        except Exception as e:
            logger.error(f"On error callback error: {e}")

    def _on_conversion_done(self):
        """Conversion completed."""
        try:
            self.is_converting = False

            elapsed = time.time() - self.conversion_start_time
            mins, secs = divmod(int(elapsed), 60)
            time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

            completed = 0
            total = 0
            if self.file_panel:
                completed = sum(1 for f in self.file_panel.files if f.status == "completed")
                total = len(self.file_panel.files)

            # Update progress to 100%
            if self.progress_bar:
                self.progress_bar.set(1.0)
            if self.progress_percent:
                self.progress_percent.configure(text="100%", text_color="#22C55E")
            if self.progress_label:
                self.progress_label.configure(text=f"Hoàn thành {completed}/{total} files")
            if self.progress_title:
                self.progress_title.configure(text="Chuyển đổi hoàn tất!")
            if self.status_badge:
                self.status_badge.configure(text="XONG", fg_color="#22C55E")
            if self.elapsed_label:
                self.elapsed_label.configure(text=f"{mins:02d}:{secs:02d}")
            if self.remaining_label:
                self.remaining_label.configure(text="00:00")
            if self.current_file_label:
                self.current_file_label.configure(text="Tất cả files đã hoàn thành!")

            # Reset convert button
            if self.btn_convert:
                self.btn_convert.configure(state="normal", text="🚀 CHUYỂN ĐỔI SANG PDF")

            # Hide progress frame after delay
            self.after(5000, self._hide_progress_frame)

            self._log(f"🎉 Hoàn thành {completed}/{total} trong {time_str}")

            if completed > 0 and self.file_panel and self.file_panel.files:
                folder = self.output_folder or str(Path(self.file_panel.files[0].path).parent)
                if messagebox.askyesno("✅ Hoàn thành",
                                       f"Đã chuyển đổi {completed}/{total} files\n"
                                       f"Thời gian: {time_str}\n\n"
                                       f"Mở folder?"):
                    os.startfile(folder)
        except Exception as e:
            logger.error(f"On conversion done error: {e}")

    def _hide_progress_frame(self):
        """Hide progress frame after completion."""
        try:
            if self.progress_frame:
                self.progress_frame.pack_forget()
        except Exception:
            pass

    def _update_time_display(self):
        """Update elapsed time display."""
        try:
            if self.is_converting:
                elapsed = time.time() - self.conversion_start_time
                mins, secs = divmod(int(elapsed), 60)

                # Update elapsed label (clean format, no icon)
                if self.elapsed_label:
                    self.elapsed_label.configure(text=f"{mins:02d}:{secs:02d}")
            
                # Keep UI responsive
                self.update_idletasks()
            
                # Schedule next update (faster for smoother display)
                self.after(500, self._update_time_display)
        except Exception as e:
            logger.error(f"Update time display error: {e}")

    # =========== UTILITIES ===========

    def _log(self, message: str):
        """Add log message with timestamp."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            if self.log_textbox:
                self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
                self.log_textbox.see("end")
            logger.info(message)
        except Exception as e:
            logger.error(f"Log error: {e}")

    def _show_stats(self):
        """Show statistics dialog."""
        try:
            stats = self.db.get_stats()

            dialog = ctk.CTkToplevel(self)
            dialog.title("📊 Thống kê")
            dialog.geometry("350x250")
            dialog.transient(self)
            dialog.grab_set()

            text = f"""
📊 THỐNG KÊ TỔNG HỢP

Tổng files: {stats['total']}
Thành công: {stats['success']}
Thất bại: {stats['failed']}
Tỷ lệ: {stats['success_rate']:.1f}%
Thời gian TB: {stats['avg_duration']:.1f}s
            """

            ctk.CTkLabel(dialog, text=text, font=ctk.CTkFont(size=14),
                        justify="left").pack(expand=True, padx=20, pady=20)

            ctk.CTkButton(dialog, text="Đóng", command=dialog.destroy).pack(pady=10)
        except Exception as e:
            logger.error(f"Show stats error: {e}")
            messagebox.showerror("Lỗi", f"Không thể hiển thị thống kê: {e}")

    def _show_settings(self):
        """Show settings dialog."""
        try:
            from office_converter.ui.dialogs import show_settings
            show_settings(self, self.config, "vi", lambda: None)
        except ImportError:
            messagebox.showinfo("Cài đặt", "Mở config.json để chỉnh sửa cài đặt")
        except Exception as e:
            logger.error(f"Show settings error: {e}")
            messagebox.showinfo("Cài đặt", "Mở config.json để chỉnh sửa cài đặt")

    def _show_shortcuts(self):
        """Show keyboard shortcuts."""
        try:
            shortcuts = """
⌨️ KEYBOARD SHORTCUTS

Ctrl+O     Thêm files
Ctrl+V     Paste files
Delete     Xóa danh sách
Enter      Bắt đầu chuyển đổi
Escape     Dừng chuyển đổi
F1         Xem shortcuts
            """
            messagebox.showinfo("Phím tắt", shortcuts)
        except Exception as e:
            logger.error(f"Show shortcuts error: {e}")

    def _on_window_restore(self, event=None):
        """Handle window restore after minimize - simple refresh."""
        # Debounce - avoid multiple triggers
        if hasattr(self, '_restore_scheduled') and self._restore_scheduled:
            return
        self._restore_scheduled = True
        
        def do_restore():
            try:
                self._restore_scheduled = False
                # Simple refresh - just update the window
                self.update_idletasks()
            except Exception:
                pass
        
        # Schedule after 100ms to debounce
        self.after(100, do_restore)

    def _open_file_tools(self):
        """Open File Tools dialog."""
        try:
            # Check if already open
            if hasattr(self, 'file_tools_dialog') and self.file_tools_dialog and self.file_tools_dialog.winfo_exists():
                self.file_tools_dialog.lift()
                self.file_tools_dialog.focus_force()
                return

            self.file_tools_dialog = FileToolsDialog(self)
            self.file_tools_dialog.grab_set() # Modal
        except Exception as e:
            logger.error(f"Error opening File Tools: {e}")
            messagebox.showerror("Error", f"Failed to open File Tools: {e}")

    def _on_closing(self):
        """Cleanup on close with forced termination."""
        try:
            logger.info("Application closing - starting cleanup")
            
            # 1. Stop conversion engine if running
            if self.engine and self.is_converting:
                logger.info("Stopping conversion engine...")
                self.engine.stop(force=True)
                # Wait a bit for threads to finish
                import time
                time.sleep(0.5)
            
            # 2. Release COM pool
            try:
                release_pool()
                logger.info("COM pool released")
            except Exception as e:
                logger.debug(f"COM pool release error: {e}")
            
            # 3. Close database connection
            try:
                if hasattr(self, 'db') and self.db:
                    if hasattr(self.db, '_conn') and self.db._conn:
                        self.db._conn.close()
                    logger.info("Database connection closed")
            except Exception as e:
                logger.debug(f"DB close error: {e}")
            
            # 4. Force kill any remaining Office processes
            try:
                import subprocess
                subprocess.run(['taskkill', '/F', '/IM', 'EXCEL.EXE'], 
                             stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                subprocess.run(['taskkill', '/F', '/IM', 'WINWORD.EXE'], 
                             stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                subprocess.run(['taskkill', '/F', '/IM', 'POWERPNT.EXE'], 
                             stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            except Exception:
                pass
            
            logger.info("Cleanup complete - forcing exit")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        finally:
            # Force exit without calling destroy() to avoid Tcl command errors
            # os._exit(0) will terminate the process immediately
            import os
            os._exit(0)


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Application entry point."""
    try:
        app = ConverterProApp()
        app.mainloop()
    except Exception as e:
        logger.error(f"Application error: {e}")
        messagebox.showerror("Lỗi nghiêm trọng", f"Ứng dụng gặp lỗi: {e}")


if __name__ == "__main__":
    main()
