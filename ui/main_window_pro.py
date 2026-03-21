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
import threading
from pathlib import Path
from typing import List, Optional, Callable

import customtkinter as ctk
from tkinter import filedialog, messagebox
from office_converter.utils.localization import get_text

# Add parent directories to path for imports
ui_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(ui_dir)
root_dir = os.path.dirname(package_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from office_converter.utils.logging_setup import setup_logging
from office_converter.utils.config import Config
# Lazy: pdf_tools and converters are loaded on-demand
# from office_converter.utils.pdf_tools import ... -> Moved to functions
# from office_converter.converters import ExcelConverter -> Moved to _convert_single

# PDF tools - loaded at module level for preview panel

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

# R3+U10: Use get_fitz() for live PyMuPDF availability check
from office_converter.core.pdf.common import get_fitz as _get_fitz_fn
fitz = _get_fitz_fn()

# ============================================================================
# CONSTANTS & CONFIGURATION
# ============================================================================

from office_converter.core.engine import (
    FileType, FILE_EXTENSIONS, ALL_EXTENSIONS, FILE_TYPE_COLORS, ConversionFile, ConversionEngine
)
from office_converter.utils.recent_files import RecentFilesDB

# B8: Mixins for God Class decomposition
from office_converter.ui.conversion_mixin import ConversionMixin
from office_converter.ui.dialogs_mixin import DialogsMixin




# ============================================================================
# FILE LIST COMPONENT — extracted to file_panel.py (R1 refactoring)
# ============================================================================
from office_converter.ui.file_panel import FileListPanel
from office_converter.ui.collapsible_section import CollapsibleSection


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

    VERSION = "4.2.112"

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
        self.var_auto_compress = ctk.BooleanVar(value=self.config.get("auto_compress", False))
        self.var_scan_mode = ctk.BooleanVar(value=self.config.get("scan_mode", False))
        self.var_password = ctk.StringVar()
        self.var_password_enabled = ctk.BooleanVar(value=False)
        self.var_page_range = ctk.StringVar(value=self.config.get("page_range", ""))
        self.var_sheet_option = ctk.IntVar(value=self.config.get("sheet_option", 0))
        self.var_sheet_index = ctk.StringVar(value=self.config.get("sheet_index", "1"))
        self.var_output_same = ctk.BooleanVar(value=self.config.get("output_same", True))
        self.var_output_folder = ctk.StringVar(value=self.config.get("output_folder", ""))
        # Setup window
        # U7: Professional title bar (no phone number)
        self.title(f"{get_text('app_title')} - v{self.VERSION}")
        self.geometry("1100x750")
        self.minsize(1000, 700)

        # Center window
        self._center_window()

        # Build UI
        self._create_layout()

        # Keyboard shortcuts
        self._setup_shortcuts()

        # F1: Restore theme from config
        saved_theme = self.config.theme
        if saved_theme == "dark":
            ctk.set_appearance_mode("dark")
            if self.theme_switch:
                self.theme_switch.select()  # Turn switch on for dark mode

        # Setup drag and drop
        self._setup_drag_drop()

        # Fix for window restore after minimize (windnd compatibility)
        self.bind('<Map>', self._on_window_restore)
        
        # Cleanup
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Initial log
        self._log(f"🚀 {get_text('app_title')} v{self.VERSION}")
        if fitz:
            self._log(get_text('pymupdf_yes'))
        else:
            self._log(get_text('pymupdf_no'))
        if HAS_TKDND:
            self._log(get_text('dnd_active_log'))

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
            w, h = 1100, 750
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
                        self._log(f"⚠️ {get_text('file_unsupported').format(basename)}")
                except Exception as file_err:
                    logger.warning(f"Skip file due to error: {file_err}")
                    continue

            if added_count > 0:
                # Refresh display
                if self.file_panel:
                    self.file_panel._refresh_display()
                self._log(f"📁 {get_text('drop_added').format(added_count)}")
                self._on_files_changed(self.file_panel.files if self.file_panel else [])
                
        except Exception as e:
            logger.error(f"Handle drop error: {e}")
            self._log(f"❌ {get_text('drop_error').format(e)}")

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

            self.btn_add_files = ctk.CTkButton(file_btn_frame, text=get_text('btn_add_file'), width=80,
                         command=self._add_files)
            self.btn_add_files.pack(side="left", padx=2)
            self.btn_add_folder = ctk.CTkButton(file_btn_frame, text=get_text('btn_add_folder'), width=80,
                         command=self._add_folder,
                         fg_color="transparent", border_width=2)
            self.btn_add_folder.pack(side="left", padx=2)
            # Paste from clipboard
            self.btn_paste = ctk.CTkButton(file_btn_frame, text="📋", width=40,
                         command=self._paste_files,
                         fg_color="transparent", border_width=2)
            self.btn_paste.pack(side="left", padx=2)
            self.btn_clear = ctk.CTkButton(file_btn_frame, text="🗑️", width=40,
                         command=self._clear_files,
                         fg_color="transparent", border_width=2,
                         hover_color="#DC2626")
            self.btn_clear.pack(side="right")
            try:
                from CTkToolTip import CTkToolTip
                CTkToolTip(self.btn_paste, message="Paste files (Ctrl+V)", delay=0.3)
                CTkToolTip(self.btn_clear, message=get_text('tooltip_clear'), delay=0.3)
            except ImportError:
                pass

            # R6: Right column — fixed 468px width (+30% from original 360px)
            right_frame = ctk.CTkFrame(self.main_content_frame, corner_radius=12)
            right_frame.pack(side="right", fill="y", padx=(5, 0))
            right_frame.configure(width=468)
            # Enforce width — don't let content shrink the frame
            right_frame.pack_propagate(False)

            # ── P3: STICKY CONVERT BUTTON (top of right panel, always visible) ──
            convert_section = ctk.CTkFrame(right_frame, fg_color="transparent")
            convert_section.pack(fill="x", padx=10, pady=(10, 5))

            self.btn_convert = ctk.CTkButton(
                convert_section,
                text=get_text('btn_convert'),
                command=self._start_conversion,
                height=48,
                font=ctk.CTkFont(size=16, weight="bold"),
                fg_color="#16A34A",
                hover_color="#15803D",
                corner_radius=10,
                state="disabled"
            )
            self.btn_convert.pack(fill="x")

            self.btn_stop = ctk.CTkButton(
                convert_section,
                text=get_text('btn_stop_convert'),
                command=self._stop_conversion,
                font=ctk.CTkFont(size=14, weight="bold"),
                fg_color="#DC2626",
                hover_color="#B91C1C",
                height=40,
                corner_radius=8
            )
            # btn_stop initially hidden — shown during conversion

            # ── P3: COMPACT INLINE PROGRESS (right panel) ──
            self.compact_progress_frame = ctk.CTkFrame(
                right_frame, fg_color="#1F2937", corner_radius=10
            )
            # Initially hidden — shown during conversion

            # Percentage + file count
            compact_top = ctk.CTkFrame(self.compact_progress_frame, fg_color="transparent")
            compact_top.pack(fill="x", padx=10, pady=(8, 2))

            self.compact_percent = ctk.CTkLabel(
                compact_top, text="0%",
                font=ctk.CTkFont(size=28, weight="bold"),
                text_color="#22C55E"
            )
            self.compact_percent.pack(side="left")

            self.compact_file_count = ctk.CTkLabel(
                compact_top, text="0/0",
                font=ctk.CTkFont(size=13),
                text_color="#9CA3AF"
            )
            self.compact_file_count.pack(side="right")

            # Compact progress bar
            self.compact_progress_bar = ctk.CTkProgressBar(
                self.compact_progress_frame,
                height=8,
                corner_radius=4,
                progress_color="#22C55E",
                fg_color="#374151"
            )
            self.compact_progress_bar.pack(fill="x", padx=10, pady=2)
            self.compact_progress_bar.set(0)

            # Time + current file row
            compact_info = ctk.CTkFrame(self.compact_progress_frame, fg_color="transparent")
            compact_info.pack(fill="x", padx=10, pady=(2, 4))

            self.compact_time = ctk.CTkLabel(
                compact_info, text="⏱ 00:00  ⏳ --:--",
                font=ctk.CTkFont(size=10),
                text_color="#9CA3AF"
            )
            self.compact_time.pack(side="left")

            compact_file_info = ctk.CTkFrame(self.compact_progress_frame, fg_color="transparent")
            compact_file_info.pack(fill="x", padx=10, pady=(0, 8))

            ctk.CTkLabel(
                compact_file_info, text="📄",
                font=ctk.CTkFont(size=11)
            ).pack(side="left")

            self.compact_current_file = ctk.CTkLabel(
                compact_file_info, text=get_text('waiting'),
                font=ctk.CTkFont(size=10),
                text_color="#D1D5DB",
                anchor="w"
            )
            self.compact_current_file.pack(side="left", padx=5, fill="x", expand=True)

            # ── OPTIONS (collapsible accordion) ──
            self._create_options_panel(right_frame)

            # ── TOOLS BUTTONS (bottom of right panel) ──
            tools_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
            tools_frame.pack(fill="x", padx=10, pady=(5, 10), side="bottom")

            self.btn_pdf = ctk.CTkButton(
                tools_frame, text=get_text('btn_pdf_tools'), width=90,
                command=self._open_pdf_tools,
                fg_color="#3B82F6", hover_color="#2563EB",
                height=30, font=ctk.CTkFont(size=11)
            )
            self.btn_pdf.pack(side="left", padx=2)
            self.btn_excel = ctk.CTkButton(
                tools_frame, text=get_text('btn_excel_tools'), width=95,
                command=self._open_excel_tools,
                fg_color="#10B981", hover_color="#059669",
                height=30, font=ctk.CTkFont(size=11)
            )
            self.btn_excel.pack(side="left", padx=2)

            ctk.CTkButton(
                tools_frame, text=get_text('btn_file_tools'), width=90,
                command=self._open_file_tools,
                fg_color="transparent", border_width=1,
                height=30, font=ctk.CTkFont(size=11)
            ).pack(side="left", padx=2)

            try:
                from CTkToolTip import CTkToolTip
                CTkToolTip(self.btn_pdf, message=get_text('tooltip_pdf'), delay=0.3)
                CTkToolTip(self.btn_excel, message=get_text('tooltip_excel'), delay=0.3)
            except ImportError:
                pass

            # === FULL PROGRESS PANEL (shown below file list during conversion) ===
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
                text=get_text('progress_converting'),
                font=ctk.CTkFont(size=16, weight="bold")
            )
            self.progress_title.pack(side="left")

            # Status badge
            self.status_badge = ctk.CTkLabel(
                header_inner,
                text=get_text('progress_status'),
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
                text=get_text('progress_files').format(0, 0),
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

            self.elapsed_title_label = ctk.CTkLabel(
                elapsed_card,
                text=get_text('time_elapsed'),
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF"
            )
            self.elapsed_title_label.pack(pady=(8, 2))

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

            self.est_title_label = ctk.CTkLabel(
                est_card,
                text=get_text('time_estimated'),
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF"
            )
            self.est_title_label.pack(pady=(8, 2))

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

            self.remaining_title_label = ctk.CTkLabel(
                remaining_card,
                text=get_text('time_remaining'),
                font=ctk.CTkFont(size=11),
                text_color="#9CA3AF"
            )
            self.remaining_title_label.pack(pady=(8, 2))

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
                text=get_text('waiting'),
                font=ctk.CTkFont(size=12),
                text_color="#D1D5DB",
                anchor="w"
            )
            self.current_file_label.pack(side="left", fill="x", expand=True)

            # === LOG ===
            log_frame = ctk.CTkFrame(self, corner_radius=12)
            log_frame.pack(fill="x", padx=15, pady=(5, 15))

            log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
            log_header.pack(fill="x", padx=10, pady=(10, 5))

            self.log_title_label = ctk.CTkLabel(log_header, text=get_text('log_label'),
                        font=ctk.CTkFont(weight="bold"))
            self.log_title_label.pack(side="left")

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

            self.log_textbox = ctk.CTkTextbox(log_frame, height=100,
                                              font=ctk.CTkFont(family="Consolas", size=11))
            self.log_textbox.pack(fill="x", padx=10, pady=(0, 10))

        except Exception as e:
            logger.error(f"Create layout error: {e}")
            messagebox.showerror(get_text('error'), get_text('layout_error').format(e))

    def _create_header(self):
        """Create header with title and controls."""
        try:
            header = ctk.CTkFrame(self, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=(15, 5))

            # Title
            title_frame = ctk.CTkFrame(header, fg_color="transparent")
            title_frame.pack(side="left")

            ctk.CTkLabel(title_frame, text=f"📄 {get_text('app_title')}",
                        font=ctk.CTkFont(size=22, weight="bold")).pack(side="left")
            ctk.CTkLabel(title_frame, text=f"v{self.VERSION}",
                        text_color="gray").pack(side="left", padx=10)
            # U7: Author in subtitle only (no phone in title bar)
            ctk.CTkLabel(title_frame, text="by TungDo",
                        text_color="#6B7280", font=ctk.CTkFont(size=11)).pack(side="left", padx=5)

            # Controls
            controls = ctk.CTkFrame(header, fg_color="transparent")
            controls.pack(side="right")

            # U8: Icon buttons with tooltips
            try:
                from CTkToolTip import CTkToolTip
                _has_tooltip = True
            except ImportError:
                _has_tooltip = False

            btn_stats = ctk.CTkButton(controls, text="📊", width=35,
                         command=self._show_stats,
                         fg_color="transparent", border_width=1)
            btn_stats.pack(side="left", padx=2)
            btn_settings = ctk.CTkButton(controls, text="⚙️", width=35,
                         command=self._show_settings,
                         fg_color="transparent", border_width=1)
            btn_settings.pack(side="left", padx=2)
            btn_help = ctk.CTkButton(controls, text="❓", width=35,
                         command=self._show_shortcuts,
                         fg_color="transparent", border_width=1)
            btn_help.pack(side="left", padx=2)

            if _has_tooltip:
                CTkToolTip(btn_stats, message=get_text('tooltip_stats'), delay=0.3)
                CTkToolTip(btn_settings, message=get_text('tooltip_settings'), delay=0.3)
                CTkToolTip(btn_help, message=get_text('tooltip_shortcuts'), delay=0.3)

            # Theme switch
            self.theme_switch = ctk.CTkSwitch(controls, text="🌙",
                                              command=self._toggle_theme)
            self.theme_switch.pack(side="left", padx=(15, 0))
            if ctk.get_appearance_mode() == "Dark":
                self.theme_switch.select()
        except Exception as e:
            logger.error(f"Create header error: {e}")

    def _create_options_panel(self, parent):
        """Create options panel with collapsible accordion sections."""
        try:
            # U3: Scrollable container for options
            scroll_container = ctk.CTkScrollableFrame(
                parent, fg_color="transparent",
                scrollbar_button_color="#4B5563"
            )
            scroll_container.pack(fill="both", expand=True, padx=5, pady=5)

            # ══════════════════════════════════════════════════
            # SECTION 1: Quality (expanded by default)
            # ══════════════════════════════════════════════════
            self.section_quality = CollapsibleSection(
                scroll_container,
                title=get_text('section_quality'),
                expanded=True
            )
            self.section_quality.pack(fill="x", pady=2)

            options = self.section_quality.content

            # Output folder
            output_frame = ctk.CTkFrame(options, fg_color="transparent")
            output_frame.pack(fill="x", pady=3)

            ctk.CTkLabel(output_frame, text=get_text('output_folder') + ":",
                        font=ctk.CTkFont(size=12)).pack(side="left")
            saved_folder = self.config.get("output_folder", "")
            if saved_folder and os.path.exists(saved_folder):
                self.output_folder = saved_folder
                output_text = os.path.basename(saved_folder)
            else:
                output_text = get_text('output_same_folder')
            self.output_label = ctk.CTkLabel(output_frame, text=output_text,
                                              text_color="gray" if not saved_folder else "#22C55E",
                                              wraplength=220)
            self.output_label.pack(side="left", padx=5)
            ctk.CTkButton(output_frame, text=get_text('btn_change'), width=50, height=25,
                         command=self._select_output,
                         fg_color="transparent", border_width=1).pack(side="right")

            # F4: Quick-pick output folder buttons
            quick_pick_frame = ctk.CTkFrame(options, fg_color="transparent")
            quick_pick_frame.pack(fill="x", pady=(0, 3))
            for label, folder_name in [("🖥️ Desktop", "Desktop"),
                                        ("📁 Documents", "Documents"),
                                        ("⬇️ Downloads", "Downloads")]:
                path = os.path.join(os.path.expanduser("~"), folder_name)
                if os.path.exists(path):
                    ctk.CTkButton(
                        quick_pick_frame, text=label, width=90, height=22,
                        font=ctk.CTkFont(size=10),
                        fg_color="transparent", border_width=1,
                        hover_color=("gray85", "gray30"),
                        command=lambda p=path: self._set_output_quick(p)
                    ).pack(side="left", padx=2)

            # Quality — 5-preset dropdown
            quality_frame = ctk.CTkFrame(options, fg_color="transparent")
            quality_frame.pack(fill="x", pady=3)

            ctk.CTkLabel(quality_frame, text=get_text('quality_pdf_label'),
                        font=ctk.CTkFont(size=12)).pack(side="left")

            self._quality_presets = [
                get_text('quality_preset_0'),
                get_text('quality_preset_1'),
                get_text('quality_preset_2'),
                get_text('quality_preset_3'),
                get_text('quality_preset_4'),
            ]
            current_preset = self._quality_presets[min(self.var_quality.get(), 4)]

            self.quality_dropdown = ctk.CTkComboBox(
                quality_frame,
                values=self._quality_presets,
                width=200,
                state="readonly",
                command=self._on_quality_dropdown_change
            )
            self.quality_dropdown.set(current_preset)
            self.quality_dropdown.pack(side="left", padx=5)

            # Quality description hint
            self._quality_hints = {
                0: get_text('quality_hint_0'),
                1: get_text('quality_hint_1'),
                2: get_text('quality_hint_2'),
                3: get_text('quality_hint_3'),
                4: get_text('quality_hint_4'),
            }
            self.quality_hint = ctk.CTkLabel(
                options, text=self._quality_hints.get(self.var_quality.get(), ""),
                text_color="gray", font=ctk.CTkFont(size=10, slant="italic")
            )
            self.quality_hint.pack(fill="x", padx=5, pady=(0, 2))

            # DPI entry row — shown only for Custom DPI
            self.dpi_frame = ctk.CTkFrame(options, fg_color="transparent")

            ctk.CTkLabel(self.dpi_frame, text=get_text('dpi_label'),
                        font=ctk.CTkFont(size=12)).pack(side="left")
            self.dpi_entry = ctk.CTkEntry(self.dpi_frame, width=60,
                                          textvariable=self.var_dpi,
                                          placeholder_text="300")
            self.dpi_entry.pack(side="left", padx=5)
            ctk.CTkLabel(self.dpi_frame, text=get_text('dpi_range'),
                        text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left")

            # FATAL-3 fix: Validate DPI on focus-out (clamp to 72-600)
            def _validate_dpi(event=None):
                try:
                    val = int(self.var_dpi.get())
                    if val < 72:
                        self.var_dpi.set("72")
                    elif val > 600:
                        self.var_dpi.set("600")
                    self.dpi_entry.configure(border_color="")
                except (ValueError, TypeError):
                    self.var_dpi.set("300")
                    self.dpi_entry.configure(border_color="#DC2626")
            self.dpi_entry.bind("<FocusOut>", _validate_dpi)
            
            self._on_quality_change()

            # Auto-compress
            self.compress_switch = ctk.CTkSwitch(
                options, text=get_text('auto_compress'),
                variable=self.var_auto_compress,
                command=self._save_auto_compress
            )
            self.compress_switch.pack(fill="x", pady=3)

            # Scan mode
            ctk.CTkSwitch(options, text=get_text('scan_mode_label'),
                         variable=self.var_scan_mode,
                         command=self._save_scan_mode).pack(fill="x", pady=3)

            # ══════════════════════════════════════════════════
            # SECTION 2: Security (collapsed by default)
            # ══════════════════════════════════════════════════
            self.section_security = CollapsibleSection(
                scroll_container,
                title=get_text('section_security'),
                expanded=False
            )
            self.section_security.pack(fill="x", pady=2)

            security_content = self.section_security.content

            pw_frame = ctk.CTkFrame(security_content, fg_color="transparent")
            pw_frame.pack(fill="x", pady=3)

            ctk.CTkSwitch(pw_frame, text=get_text('password_pdf'),
                         variable=self.var_password_enabled,
                         command=self._on_password_toggle).pack(side="left")
            self.password_entry = ctk.CTkEntry(pw_frame, textvariable=self.var_password,
                                               show="*", width=120, state="disabled",
                                               placeholder_text=get_text('password_placeholder'))
            self.password_entry.pack(side="left", padx=5)

            # ══════════════════════════════════════════════════
            # SECTION 3: Excel (collapsed by default)
            # ══════════════════════════════════════════════════
            self.section_excel = CollapsibleSection(
                scroll_container,
                title=get_text('section_excel'),
                expanded=False
            )
            self.section_excel.pack(fill="x", pady=2)

            excel_content = self.section_excel.content

            sheet_frame = ctk.CTkFrame(excel_content, fg_color="transparent")
            sheet_frame.pack(fill="x", pady=3)

            ctk.CTkLabel(sheet_frame, text=get_text('sheet_label'),
                        font=ctk.CTkFont(size=12)).pack(side="left")
            sheet_entry = ctk.CTkEntry(sheet_frame, textvariable=self.var_sheet_index,
                        width=80, placeholder_text="all")
            sheet_entry.pack(side="left", padx=5)
            ctk.CTkLabel(sheet_frame, text="VD: 1-3, 5", 
                        text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left")

            page_frame = ctk.CTkFrame(excel_content, fg_color="transparent")
            page_frame.pack(fill="x", pady=3)

            ctk.CTkLabel(page_frame, text=get_text('page_label'),
                        font=ctk.CTkFont(size=12)).pack(side="left")
            page_entry = ctk.CTkEntry(page_frame, textvariable=self.var_page_range,
                        width=80, placeholder_text="all")
            page_entry.pack(side="left", padx=5)
            ctk.CTkLabel(page_frame, text=get_text('page_hint'), 
                        text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left")
            page_entry.bind("<FocusOut>", lambda e: self._save_page_range())
        except Exception as e:
            logger.error(f"Create options error: {e}")

    def _on_quality_dropdown_change(self, selected: str):
        """Handle quality dropdown selection."""
        try:
            idx = self._quality_presets.index(selected)
            self.var_quality.set(idx)
            self._on_quality_change()
        except (ValueError, Exception):
            pass

    def _on_quality_change(self):
        """Handle quality selection change."""
        try:
            val = self.var_quality.get()
            if val == 4:  # Custom DPI
                # Show DPI row below quality dropdown
                self.dpi_entry.configure(state="normal")
                self.dpi_frame.pack(fill="x", pady=3, before=self.compress_switch)
            else:
                # Hide DPI row
                self.dpi_frame.pack_forget()
                self.dpi_entry.configure(state="disabled")
            
            # Update quality hint text
            if hasattr(self, 'quality_hint') and hasattr(self, '_quality_hints'):
                hint = self._quality_hints.get(val, "")
                self.quality_hint.configure(text=hint)
            
            # Auto-enable compress for quality >= 1
            if val >= 1 and val <= 3:
                self.var_auto_compress.set(True)
            elif val == 0:
                self.var_auto_compress.set(False)
            
            self._save_quality()
        except Exception:
            pass

    def _save_quality(self):
        """Save quality setting to config."""
        try:
            self.config.set("pdf_quality", self.var_quality.get())
            self.config.set("auto_compress", self.var_auto_compress.get())
            if self.var_quality.get() == 4:
                self.config.set("pdf_dpi", self.var_dpi.get())
            self.config.save()
        except Exception as e:
            logger.error(f"Save quality error: {e}")

    def _save_auto_compress(self):
        """Save auto-compress setting to config."""
        try:
            self.config.set("auto_compress", self.var_auto_compress.get())
            self.config.save()
        except Exception as e:
            logger.error(f"Save auto_compress error: {e}")

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
        """Called when file list changes. Updates convert button state + pulse animation."""
        try:
            count = len(files)
            has_files = count > 0
            if self.btn_convert:
                if has_files and not self.is_converting:
                    # Show file count on button
                    self.btn_convert.configure(
                        state="normal",
                        text=f"✏ {get_text('btn_convert')}  ({count})"
                    )
                    # Pulse animation: briefly brighten the button
                    self._pulse_convert_button()
                elif not has_files:
                    self.btn_convert.configure(
                        state="disabled",
                        text=get_text('btn_convert')
                    )
        except Exception as e:
            logger.error(f"On files changed error: {e}")

    def _pulse_convert_button(self):
        """Brief pulse animation on convert button when files change."""
        try:
            if not hasattr(self, '_pulse_job'):
                self._pulse_job = None
            # Cancel previous pulse
            if self._pulse_job:
                self.after_cancel(self._pulse_job)
            # Brighten
            self.btn_convert.configure(fg_color="#22C55E")
            # Restore after 300ms
            self._pulse_job = self.after(
                300,
                lambda: self.btn_convert.configure(fg_color="#16A34A")
            )
        except Exception:
            pass

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
        """Toggle dark/light theme. F1: Persist to config."""
        try:
            if self.theme_switch:
                mode = "dark" if self.theme_switch.get() else "light"
                ctk.set_appearance_mode(mode)
                # F1: Save theme preference to config
                self.config.theme = mode
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
                    self._log(get_text("drop_added").format(added))
        except Exception as e:
            logger.error(f"Add files error: {e}")
            messagebox.showerror(get_text('error'), get_text('add_files_error').format(e))

    def _add_folder(self):
        """Add files from folder. R4: Threaded scan with progress indicator."""
        try:
            folder = filedialog.askdirectory()
            if not folder or not self.file_panel:
                return

            self._log(get_text('scanning_folder').format(os.path.basename(folder)))

            # R4: Run folder scan in thread to avoid blocking UI
            def _scan_folder():
                try:
                    files = []
                    max_depth = 5  # R4: Depth limit to avoid scanning huge trees
                    base_depth = folder.count(os.sep)
                    for root, dirs, filenames in os.walk(folder):
                        # Check depth
                        current_depth = root.count(os.sep) - base_depth
                        if current_depth >= max_depth:
                            dirs.clear()  # Don't descend further
                            continue
                        for f in filenames:
                            ext = Path(f).suffix.lower()
                            if ext in ALL_EXTENSIONS:
                                files.append(os.path.join(root, f))

                    # Update UI on main thread
                    def _update_ui():
                        if files:
                            added = self.file_panel.add_files(files)
                            self._log(get_text('folder_added').format(added))
                        else:
                            self._log(get_text('no_office_files'))
                    self.after(0, _update_ui)
                except Exception as scan_err:
                    self.after(0, lambda err=scan_err: self._log(get_text('folder_scan_error').format(err)))

            threading.Thread(target=_scan_folder, daemon=True).start()
        except Exception as e:
            logger.error(f"Add folder error: {e}")
            messagebox.showerror(get_text('error'), get_text('add_files_error').format(e))

    # _show_recent() → DialogsMixin

    def _paste_files(self):
        """R5: Real Ctrl+V — paste file paths from Windows clipboard."""
        try:
            import ctypes

            # Windows clipboard constants
            CF_HDROP = 15
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32

            if not user32.OpenClipboard(0):
                self._log(get_text('clipboard_error'))
                return

            try:
                h_drop = user32.GetClipboardData(CF_HDROP)
                if not h_drop:
                    # Try text clipboard fallback
                    CF_UNICODETEXT = 13
                    h_text = user32.GetClipboardData(CF_UNICODETEXT)
                    if h_text:
                        text_ptr = kernel32.GlobalLock(h_text)
                        if text_ptr:
                            text = ctypes.wstring_at(text_ptr)
                            kernel32.GlobalUnlock(h_text)
                            # Parse as file paths (one per line)
                            paths = [p.strip().strip('"') for p in text.splitlines() if p.strip()]
                            valid = [p for p in paths if os.path.isfile(p)]
                            if valid and self.file_panel:
                                added = self.file_panel.add_files(valid)
                                self._log(get_text('clipboard_paste_ok').format(added))
                                return
                    self._log(get_text('clipboard_empty'))
                    return

                # Extract file paths from HDROP
                count = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
                paths = []
                for i in range(count):
                    buf_size = shell32.DragQueryFileW(h_drop, i, None, 0) + 1
                    buf = ctypes.create_unicode_buffer(buf_size)
                    shell32.DragQueryFileW(h_drop, i, buf, buf_size)
                    paths.append(buf.value)

                if paths and self.file_panel:
                    added = self.file_panel.add_files(paths)
                    self._log(get_text('clipboard_paste_ok').format(added))
                else:
                    self._log(get_text('clipboard_no_supported'))
            finally:
                user32.CloseClipboard()
        except Exception as e:
            logger.error(f"Paste files error: {e}")
            self._log(get_text('clipboard_paste_failed'))

    def _change_language(self, selected_name: str):
        """Change application language with instant hot-reload."""
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
                self.config.set("language", lang_code, auto_save=False)
                self.config.save()
                set_language(lang_code)

                # Hot-reload: update all UI text instantly
                self._apply_language()

                self._log(get_text('lang_changed').format(selected_name))
        except Exception as e:
            logger.error(f"Change language error: {e}")

    def _apply_language(self):
        """Hot-reload: Re-apply all UI text from current language.
        
        Updates stored widget references with get_text() values.
        No restart needed — instant language switching.
        """
        try:
            # Window title
            self.title(f"{get_text('app_title')} - v{self.VERSION}")

            # Main convert button
            if self.btn_convert:
                self.btn_convert.configure(text=get_text('btn_convert'))

            # Stop button
            if self.btn_stop:
                self.btn_stop.configure(text=get_text('btn_stop_convert'))

            # File action buttons
            for attr, key in [
                ('btn_add_files', 'btn_add_file'),
                ('btn_add_folder', 'btn_add_folder'),
                ('btn_pdf', 'btn_pdf_tools'),
                ('btn_excel', 'btn_excel_tools'),
            ]:
                widget = getattr(self, attr, None)
                if widget:
                    widget.configure(text=get_text(key))

            # Progress section (if visible)
            if self.progress_title:
                self.progress_title.configure(text=get_text('progress_converting'))
            if self.status_badge:
                self.status_badge.configure(text=get_text('progress_status'))
            if self.current_file_label:
                self.current_file_label.configure(text=get_text('waiting'))

            # Time card title labels
            for attr, key in [
                ('elapsed_title_label', 'time_elapsed'),
                ('est_title_label', 'time_estimated'),
                ('remaining_title_label', 'time_remaining'),
            ]:
                widget = getattr(self, attr, None)
                if widget:
                    widget.configure(text=get_text(key))

            # Log header
            if hasattr(self, 'log_title_label') and self.log_title_label:
                self.log_title_label.configure(text=get_text('log_label'))

            # Quality presets (reload)
            if hasattr(self, '_quality_presets') and hasattr(self, 'quality_dropdown'):
                self._quality_presets = [
                    get_text('quality_preset_0'),
                    get_text('quality_preset_1'),
                    get_text('quality_preset_2'),
                    get_text('quality_preset_3'),
                    get_text('quality_preset_4'),
                ]
                self.quality_dropdown.configure(values=self._quality_presets)
                idx = self.var_quality.get()
                self.quality_dropdown.set(self._quality_presets[min(idx, 4)])

            # Quality hints (reload)
            if hasattr(self, '_quality_hints') and hasattr(self, 'quality_hint'):
                self._quality_hints = {
                    0: get_text('quality_hint_0'),
                    1: get_text('quality_hint_1'),
                    2: get_text('quality_hint_2'),
                    3: get_text('quality_hint_3'),
                    4: get_text('quality_hint_4'),
                }
                val = self.var_quality.get()
                self.quality_hint.configure(text=self._quality_hints.get(val, ""))

            # Compress switch
            if hasattr(self, 'compress_switch'):
                self.compress_switch.configure(text=get_text('auto_compress'))

            logger.info("Language hot-reload applied successfully")
        except Exception as e:
            logger.error(f"Apply language error: {e}")

    def _open_pdf_tools(self):
        """Open PDF Tools Pro dialog."""
        try:
            from office_converter.ui.pdf_tools_pro import PDFToolsDialogPro
            PDFToolsDialogPro(self, "vi")
        except Exception as e:
            logger.error(f"Open PDF Tools error: {e}")
            messagebox.showerror(get_text('error'), get_text('open_pdf_tools_error').format(e))

    def _open_excel_tools(self):
        """Open Excel Tools dialog."""
        try:
            from office_converter.ui.excel_tools_ui import ExcelToolsDialog
            ExcelToolsDialog(self, "vi")
        except ImportError as e:
            logger.error(f"Excel Tools import error: {e}")
            messagebox.showerror(
                get_text('error'),
                get_text('missing_openpyxl')
            )
        except Exception as e:
            logger.error(f"Open Excel Tools error: {e}")
            messagebox.showerror(get_text('error'), get_text('open_excel_error').format(e))

    def _clear_files(self):
        """Clear file list. U6: Confirm before clearing >3 files."""
        try:
            if self.file_panel and self.file_panel.files:
                count = len(self.file_panel.files)
                # U6: Confirmation for large lists
                if count > 3:
                    if not messagebox.askyesno(
                        get_text('confirm_clear_title'),
                        get_text('confirm_clear_msg').format(count)
                    ):
                        return
                self.file_panel.clear()
                self._log(get_text('files_cleared').format(count))
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
                self.config.set("output_folder", folder, auto_save=False)
                self.config.save()
        except Exception as e:
            logger.error(f"Select output error: {e}")

    def _set_output_quick(self, folder: str):
        """F4: Quick-set output folder from Desktop/Documents/Downloads buttons."""
        try:
            if os.path.exists(folder):
                self.output_folder = folder
                display = Path(folder).name
                if self.output_label:
                    self.output_label.configure(text=display, text_color="#22C55E")
                self.config.set("output_folder", folder, auto_save=False)
                self.config.save()
                self._log(f"📁 Output → {display}")
        except Exception as e:
            logger.error(f"Set output quick error: {e}")

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
