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
# FileToolsDialog - lazy loaded in _open_file_tools()

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

from office_converter.core.engine import (
    FileType, FILE_EXTENSIONS, ALL_EXTENSIONS, FILE_TYPE_COLORS, FILE_TYPE_ICONS,
    ConversionFile, ConversionOptions, ConversionEngine
)
from office_converter.utils.recent_files import RecentFilesDB

# B8: Mixins for God Class decomposition
from office_converter.ui.conversion_mixin import ConversionMixin
from office_converter.ui.dialogs_mixin import DialogsMixin




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

class ConverterProApp(ConversionMixin, DialogsMixin, TkDnDWrapper):
    """Professional-grade Office to PDF Converter.
    
    B8: Decomposed via Mixin pattern:
    - ConversionMixin: conversion start/stop, progress, callbacks
    - DialogsMixin: dialogs, logging, settings, lifecycle
    - ConverterProApp: UI layout, options, file actions, DnD
    """

    VERSION = "4.2.100"

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

        # B3: Throttle state for UI updates during batch conversion
        self._last_progress_update = 0.0  # timestamp of last progress UI push
        self._progress_throttle_ms = 100  # minimum ms between progress updates
        self._log_buffer: list = []  # buffered log messages
        self._log_flush_job = None  # scheduled flush job ID
        self._anim_target = 0.0  # current animation target (coalesce)

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

    # _show_recent() → DialogsMixin

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
    # _start_conversion, _calculate_estimated_time, _run_conversion,
    # _stop_conversion, _on_progress, _update_progress_ui,
    # _animate_progress, _on_file_complete, _flush_log_buffer,
    # _on_error, _on_conversion_done, _hide_progress_frame,
    # _update_time_display → ConversionMixin

    # =========== UTILITIES ===========
    # _log, _show_stats, _show_settings, _show_shortcuts,
    # _show_recent, _on_window_restore, _open_file_tools,
    # _on_closing → DialogsMixin


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
# EOF — methods below this point are provided by mixins via MRO
