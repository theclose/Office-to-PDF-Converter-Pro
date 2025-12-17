"""
Office Converter - Complete UI
Full-featured interface for converting Office documents to PDF.
Supports: Excel, Word, PowerPoint
"""

import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Optional

# Add parent directories to path for imports
ui_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(ui_dir)
root_dir = os.path.dirname(package_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from office_converter.utils.logging_setup import setup_logging, get_logger
from office_converter.utils.config import Config
from office_converter.utils.localization import get_text, set_language, get_language_names, LANGUAGES
from office_converter.utils.pdf_tools import (
    post_process_pdf, rasterize_pdf, merge_pdfs, split_pdf, 
    parse_page_range, extract_pdf_pages, HAS_PYMUPDF
)
from office_converter.utils.com_pool import release_pool
from office_converter.utils.history import get_history
from office_converter import __version__
from office_converter.utils.progress_estimator import estimate_conversion_time, log_conversion_result
from office_converter.converters import get_converter_for_file, ExcelConverter, WordConverter, PPTConverter
from office_converter.ui.dialogs import show_settings

logger = get_logger("ui")

# Try to import windnd for drag-drop (optional)
try:
    import windnd
    HAS_WINDND = True
except ImportError:
    HAS_WINDND = False

# All supported file extensions
ALL_EXTENSIONS = (
    ExcelConverter.SUPPORTED_EXTENSIONS + 
    WordConverter.SUPPORTED_EXTENSIONS + 
    PPTConverter.SUPPORTED_EXTENSIONS
)


class ConverterApp:
    """Complete Office to PDF Converter Application."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.config = Config()
        self.current_lang = self.config.language
        self.current_theme = self.config.theme
        
        # State
        self.file_list: List[str] = []
        self.completed_files: set = set()  # Track completed file paths
        self.is_converting = False
        self.stop_requested = False      # Flag to request stop
        self.stopped_at_index = 0        # Track where we stopped for resume
        self.output_folder = self.config.get("output_folder", "")
        
        # Setup window
        self.root.title(f"{get_text('app_title', self.current_lang)} - v{__version__}")
        self.root.geometry("700x800")
        self.root.minsize(680, 750)
        
        # Variables
        self.var_quality = tk.IntVar(value=self.config.pdf_quality)
        self.var_scan_mode = tk.BooleanVar(value=self.config.get("scan_mode", False))
        self.var_password = tk.StringVar()
        self.var_password_enabled = tk.BooleanVar(value=False)
        self.var_author = tk.StringVar()
        self.var_title = tk.StringVar()
        self.var_page_range = tk.StringVar()
        self.var_sheet_option = tk.IntVar(value=0)  # 0=All sheets, 1=Specific
        self.var_sheet_index = tk.StringVar(value="1")
        
        # Apply theme
        self._apply_theme()
        
        # Build UI
        self._create_widgets()
        
        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.add_files())
        self.root.bind('<Control-O>', lambda e: self.add_files())
        self.root.bind('<Delete>', lambda e: self.delete_selected())
        self.root.bind('<Return>', lambda e: self.start_conversion() if not self.is_converting else None)
        
        # Ensure window is visible and centered
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 650
        window_height = 750
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Force window to appear on top and get focus
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.focus_force()
    
    def _apply_theme(self):
        """Apply eye-friendly professional theme."""
        style = ttk.Style()
        
        try:
            style.theme_use('clam')
        except Exception:
            pass
        
        # === EYE-FRIENDLY COLOR PALETTES ===
        if self.current_theme == "dark":
            # Dark Mode - Warm gray like Discord/Slack (not harsh black)
            colors = {
                'bg_primary': '#36393F',      # Warm dark gray (Discord-like)
                'bg_secondary': '#2F3136',    # Slightly darker
                'bg_tertiary': '#40444B',     # Input fields
                'bg_hover': '#4F545C',        # Hover
                'bg_active': '#5865F2',       # Active/Selected (Discord purple)
                'text_primary': '#DCDDDE',    # Soft white (not harsh)
                'text_secondary': '#96989D',  # Muted
                'text_bright': '#FFFFFF',     # Emphasis
                'accent': '#5865F2',          # Discord blurple
                'accent_hover': '#4752C4',    # Darker accent
                'success': '#57F287',         # Discord green
                'warning': '#FEE75C',         # Discord yellow
                'error': '#ED4245',           # Discord red
                'border': '#4F545C',          # Subtle border
            }
            listbox_bg = '#2F3136'
            listbox_fg = '#DCDDDE'
            listbox_select_bg = '#5865F2'
            listbox_select_fg = '#FFFFFF'
            log_bg = '#2F3136'
        else:
            # Light Mode - Warm cream/off-white (not harsh pure white)
            colors = {
                'bg_primary': '#FAF9F6',      # Warm off-white/cream
                'bg_secondary': '#F0EDE5',    # Slightly tan
                'bg_tertiary': '#FFFFFF',     # Pure white for inputs only
                'bg_hover': '#E8E4DB',        # Warm hover
                'bg_active': '#D4E5F7',       # Soft blue selection
                'text_primary': '#1D1C1A',    # Warm black (not harsh)
                'text_secondary': '#6B6966',  # Warm gray
                'text_bright': '#000000',     # Pure black for emphasis
                'accent': '#1A73E8',          # Google blue
                'accent_hover': '#1557B0',    # Darker blue
                'success': '#188038',         # Google green
                'warning': '#E37400',         # Warm orange
                'error': '#D93025',           # Google red
                'border': '#DAD7CE',          # Warm border
            }
            listbox_bg = '#FFFFFF'
            listbox_fg = '#1D1C1A'
            listbox_select_bg = '#D4E5F7'
            listbox_select_fg = '#1A73E8'
            log_bg = '#FDFCFA'
        
        # === APPLY STYLES ===
        
        # Root window
        self.root.configure(bg=colors['bg_primary'])
        
        # Frame
        style.configure("TFrame", background=colors['bg_primary'])
        
        # Labels
        style.configure("TLabel", 
                       background=colors['bg_primary'], 
                       foreground=colors['text_primary'],
                       font=('Segoe UI', 10))
        
        # LabelFrame - Use secondary bg for cards
        style.configure("TLabelframe", 
                       background=colors['bg_secondary'])
        style.configure("TLabelframe.Label", 
                       background=colors['bg_secondary'],
                       foreground=colors['text_primary'],
                       font=('Segoe UI', 10, 'bold'))
        
        # Buttons
        style.configure("TButton",
                       background=colors['bg_secondary'],
                       foreground=colors['text_primary'],
                       bordercolor=colors['border'],
                       padding=(10, 5),
                       font=('Segoe UI', 9))
        style.map("TButton",
                 background=[('active', colors['bg_hover']),
                            ('pressed', colors['accent'])],
                 foreground=[('pressed', '#FFFFFF')])
        
        # EMERGENCY STOP BUTTON - Bright red like real emergency stop
        style.configure("Emergency.TButton",
                       background='#DC2626',  # Bright red
                       foreground='#FFFFFF',  # White text
                       bordercolor='#991B1B',
                       padding=(12, 6),
                       font=('Segoe UI', 10, 'bold'))
        style.map("Emergency.TButton",
                 background=[('active', '#B91C1C'),    # Darker red on hover
                            ('pressed', '#7F1D1D')],   # Even darker on press
                 foreground=[('active', '#FFFFFF'),
                            ('pressed', '#FFFFFF')])
        
        # RESUME BUTTON - Green color
        style.configure("Resume.TButton",
                       background='#16A34A',  # Green
                       foreground='#FFFFFF',  # White text
                       bordercolor='#15803D',
                       padding=(12, 6),
                       font=('Segoe UI', 10, 'bold'))
        style.map("Resume.TButton",
                 background=[('active', '#15803D'),
                            ('pressed', '#166534')],
                 foreground=[('active', '#FFFFFF'),
                            ('pressed', '#FFFFFF')])
        
        # Checkbutton & Radiobutton
        style.configure("TCheckbutton",
                       background=colors['bg_secondary'],
                       foreground=colors['text_primary'])
        style.map("TCheckbutton",
                 background=[('active', colors['bg_secondary'])])
        
        style.configure("TRadiobutton",
                       background=colors['bg_secondary'],
                       foreground=colors['text_primary'])
        style.map("TRadiobutton",
                 background=[('active', colors['bg_secondary'])])
        
        # Entry
        style.configure("TEntry",
                       fieldbackground=colors['bg_tertiary'],
                       foreground=colors['text_primary'],
                       bordercolor=colors['border'])
        
        # Combobox
        style.configure("TCombobox",
                       fieldbackground=colors['bg_tertiary'],
                       background=colors['bg_secondary'],
                       foreground=colors['text_primary'])
        
        # Progress bar
        style.configure("TProgressbar",
                       background=colors['accent'],
                       troughcolor=colors['bg_secondary'],
                       bordercolor=colors['border'])
        
        # Scrollbar
        style.configure("TScrollbar",
                       background=colors['bg_secondary'],
                       troughcolor=colors['bg_primary'],
                       bordercolor=colors['border'])
        
        # Store colors
        self.colors = colors
        
        # Update listbox
        if hasattr(self, 'listbox'):
            self.listbox.configure(
                bg=listbox_bg,
                fg=listbox_fg,
                selectbackground=listbox_select_bg,
                selectforeground=listbox_select_fg,
                font=('Segoe UI', 10),
                highlightthickness=1,
                highlightbackground=colors['border'],
                highlightcolor=colors['accent'],
                borderwidth=0,
                relief='flat'
            )
        
        # Update log text
        if hasattr(self, 'txt_log'):
            self.txt_log.configure(
                bg=log_bg,
                fg=colors['text_primary'],
                font=('Consolas', 9),
                insertbackground=colors['text_primary'],
                highlightthickness=1,
                highlightbackground=colors['border'],
                highlightcolor=colors['accent'],
                borderwidth=0,
                relief='flat'
            )
    
    def toggle_theme(self):
        """Toggle dark/light theme."""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.config.theme = self.current_theme
        self._apply_theme()
        # Update button text
        if self.current_theme == "dark":
            self.btn_theme.config(text=get_text("btn_light", self.current_lang))
        else:
            self.btn_theme.config(text=get_text("btn_dark", self.current_lang))
    
    def _create_widgets(self):
        """Create all UI widgets."""
        
        # === 1. FILE LIST ===
        self.frame_files = ttk.LabelFrame(self.root, text=get_text("file_list_title", self.current_lang), padding=5)
        self.frame_files.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Listbox with scrollbar
        self.listbox = tk.Listbox(self.frame_files, selectmode=tk.EXTENDED, height=8, font=("Segoe UI", 10))
        self.listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(self.frame_files, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        # === 2. BUTTONS ROW 1: File operations + Convert ===
        frame_btns1 = ttk.Frame(self.root)
        frame_btns1.pack(fill="x", padx=10, pady=3)
        
        self.btn_add = ttk.Button(frame_btns1, text=get_text("btn_add_file", self.current_lang), command=self.add_files)
        self.btn_add.pack(side="left", padx=2)
        
        self.btn_folder = ttk.Button(frame_btns1, text=get_text("btn_add_folder", self.current_lang), command=self.add_folder)
        self.btn_folder.pack(side="left", padx=2)
        
        self.btn_clear = ttk.Button(frame_btns1, text=get_text("btn_clear", self.current_lang), command=self.clear_list)
        self.btn_clear.pack(side="left", padx=2)
        
        # Theme toggle
        theme_text = get_text("btn_light", self.current_lang) if self.current_theme == "dark" else get_text("btn_dark", self.current_lang)
        self.btn_theme = ttk.Button(frame_btns1, text=theme_text, command=self.toggle_theme)
        self.btn_theme.pack(side="left", padx=2)
        
        # STOP/RESUME BUTTON (hidden initially, shows during conversion)
        self.btn_stop = ttk.Button(frame_btns1, text=get_text("btn_stop", self.current_lang), 
                                   style="Emergency.TButton", command=self._toggle_stop_resume)
        # Don't pack yet - will show during conversion
        
        # CONVERT BUTTON (prominent)
        self.btn_convert = ttk.Button(frame_btns1, text=get_text("btn_convert", self.current_lang), command=self.start_conversion)
        self.btn_convert.pack(side="right", padx=2)
        
        # === 3. BUTTONS ROW 2: PDF Tools & Settings ===
        frame_btns2 = ttk.Frame(self.root)
        frame_btns2.pack(fill="x", padx=10, pady=3)
        
        self.lbl_pdf_tools = ttk.Label(frame_btns2, text=get_text("pdf_tools", self.current_lang))
        self.lbl_pdf_tools.pack(side="left")
        
        # PDF Tools Dialog button (opens unified dialog with ALL PDF operations)
        self.btn_pdf_tools = ttk.Button(frame_btns2, text="🛠️ PDF Tools...", command=self.open_pdf_tools_dialog)
        self.btn_pdf_tools.pack(side="left", padx=5)
        
        # Settings and History buttons
        ttk.Button(frame_btns2, text="⚙️", width=3, command=self.show_settings).pack(side="left", padx=5)
        ttk.Button(frame_btns2, text="📊", width=3, command=self.show_history).pack(side="left", padx=2)
        
        # Language selector (on right)
        ttk.Label(frame_btns2, text="🌐").pack(side="right", padx=(10, 0))
        self.combo_lang = ttk.Combobox(frame_btns2, width=10, state="readonly",
                                        values=list(get_language_names().values()))
        self.combo_lang.set(LANGUAGES[self.current_lang]["name"])
        self.combo_lang.pack(side="right")
        self.combo_lang.bind("<<ComboboxSelected>>", self._on_language_change)
        
        # === 5. OUTPUT FOLDER ===
        frame_output = ttk.Frame(self.root)
        frame_output.pack(fill="x", padx=10, pady=3)
        
        self.lbl_output_title = ttk.Label(frame_output, text=get_text("output_folder", self.current_lang))
        self.lbl_output_title.pack(side="left")
        self.lbl_output = ttk.Label(frame_output, text=self.output_folder or get_text("output_default", self.current_lang),
                                    foreground="gray")
        self.lbl_output.pack(side="left", padx=5)
        self.btn_select = ttk.Button(frame_output, text=get_text("btn_select", self.current_lang), command=self.select_output_folder)
        self.btn_select.pack(side="right")
        self.btn_reset = ttk.Button(frame_output, text=get_text("btn_reset", self.current_lang), command=self.reset_output_folder)
        self.btn_reset.pack(side="right", padx=2)
        
        # === 5. PDF OPTIONS ===
        self.frame_options = ttk.LabelFrame(self.root, text=get_text("options_title", self.current_lang), padding=5)
        self.frame_options.pack(fill="x", padx=10, pady=5)
        
        # Sheet selection (Excel only)
        frame_sheets = ttk.Frame(self.frame_options)
        frame_sheets.pack(fill="x", pady=2)
        
        self.rb_all_sheets = ttk.Radiobutton(frame_sheets, text=get_text("all_sheets", self.current_lang),
                                              variable=self.var_sheet_option, value=0)
        self.rb_all_sheets.pack(side="left")
        
        self.rb_specific = ttk.Radiobutton(frame_sheets, text=get_text("specific_sheets", self.current_lang),
                                            variable=self.var_sheet_option, value=1)
        self.rb_specific.pack(side="left", padx=10)
        
        self.entry_sheet = ttk.Entry(frame_sheets, textvariable=self.var_sheet_index, width=15)
        self.entry_sheet.pack(side="left")
        
        self.lbl_sheet_hint = ttk.Label(frame_sheets, text=get_text("sheet_hint", self.current_lang), foreground="gray")
        self.lbl_sheet_hint.pack(side="left", padx=5)
        
        # Quality + Scan mode
        frame_quality = ttk.Frame(self.frame_options)
        frame_quality.pack(fill="x", pady=2)
        
        self.lbl_quality = ttk.Label(frame_quality, text=get_text("quality_label", self.current_lang))
        self.lbl_quality.pack(side="left")
        self.rb_quality_high = ttk.Radiobutton(frame_quality, text=get_text("quality_high", self.current_lang),
                                                variable=self.var_quality, value=0)
        self.rb_quality_high.pack(side="left", padx=5)
        self.rb_quality_min = ttk.Radiobutton(frame_quality, text=get_text("quality_min", self.current_lang),
                                               variable=self.var_quality, value=1)
        self.rb_quality_min.pack(side="left")
        
        # Scan mode checkbox (always show)
        self.chk_scan = ttk.Checkbutton(frame_quality, text=get_text("scan_mode", self.current_lang),
                                        variable=self.var_scan_mode)
        self.chk_scan.pack(side="right")
        
        # === 6. SECURITY & METADATA ===
        self.frame_security = ttk.LabelFrame(self.root, text=get_text("security_label", self.current_lang), padding=5)
        self.frame_security.pack(fill="x", padx=10, pady=5)
        
        # Password
        frame_pw = ttk.Frame(self.frame_security)
        frame_pw.pack(fill="x", pady=2)
        
        self.chk_password = ttk.Checkbutton(frame_pw, text=get_text("password_label", self.current_lang),
                                             variable=self.var_password_enabled)
        self.chk_password.pack(side="left")
        self.entry_password = ttk.Entry(frame_pw, textvariable=self.var_password, show="*", width=20)
        self.entry_password.pack(side="left", padx=5)
        
        # Author + Title
        frame_meta = ttk.Frame(self.frame_security)
        frame_meta.pack(fill="x", pady=2)
        
        self.lbl_author = ttk.Label(frame_meta, text=get_text("author_label", self.current_lang))
        self.lbl_author.pack(side="left")
        self.entry_author = ttk.Entry(frame_meta, textvariable=self.var_author, width=12)
        self.entry_author.pack(side="left", padx=2)
        
        self.lbl_title = ttk.Label(frame_meta, text=get_text("title_label", self.current_lang))
        self.lbl_title.pack(side="left", padx=(10, 0))
        self.entry_title = ttk.Entry(frame_meta, textvariable=self.var_title, width=15)
        self.entry_title.pack(side="left", padx=2)
        
        # Page range
        frame_pages = ttk.Frame(self.frame_security)
        frame_pages.pack(fill="x", pady=2)
        
        self.lbl_page_range = ttk.Label(frame_pages, text=get_text("page_range", self.current_lang))
        self.lbl_page_range.pack(side="left")
        self.entry_pages = ttk.Entry(frame_pages, textvariable=self.var_page_range, width=20)
        self.entry_pages.pack(side="left", padx=5)
        self.lbl_page_hint = ttk.Label(frame_pages, text=get_text("page_hint", self.current_lang), foreground="gray")
        self.lbl_page_hint.pack(side="left")
        
        # === 7. PROGRESS ===
        # Create custom header frame for LabelFrame
        frame_progress_header = ttk.Frame(self.root)
        
        # Title on left
        lbl_progress_title = ttk.Label(frame_progress_header, text=get_text("progress_title", self.current_lang), 
                                       font=("Segoe UI", 9, "bold"))
        lbl_progress_title.pack(side="left")
        
        # Time displays in header (order: Estimated | Elapsed | Remaining)
        # Pack in reverse order because side="right" stacks from right
        self.lbl_remaining_time = ttk.Label(frame_progress_header, text="", foreground="orange")
        self.lbl_remaining_time.pack(side="right", padx=(15, 0))
        
        self.lbl_elapsed_time = ttk.Label(frame_progress_header, text="", foreground="cyan")
        self.lbl_elapsed_time.pack(side="right", padx=(15, 0))
        
        self.lbl_estimated_time = ttk.Label(frame_progress_header, text="", foreground="gray")
        self.lbl_estimated_time.pack(side="right", padx=(20, 0))
        
        self.frame_progress = ttk.LabelFrame(self.root, labelwidget=frame_progress_header, padding=5)
        self.frame_progress.pack(fill="x", padx=10, pady=5)
        
        # Status label
        self.lbl_status = ttk.Label(self.frame_progress, text=get_text("status_ready", self.current_lang))
        self.lbl_status.pack(fill="x")
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(self.frame_progress, style="green.Horizontal.TProgressbar",
                                            length=100, mode="determinate")
        self.progress_bar.pack(fill="x", pady=2)
        
        # === 8. LOG ===
        self.frame_log = ttk.LabelFrame(self.root, text=get_text("log_title", self.current_lang), padding=5)
        self.frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.txt_log = tk.Text(self.frame_log, height=6, font=("Consolas", 9), wrap="word")
        self.txt_log.pack(fill="both", expand=True)
    
    # === FILE OPERATIONS ===
    
    def log(self, message: str):
        """Add message to log."""
        self.txt_log.insert("end", message + "\n")
        self.txt_log.see("end")
        logger.info(message)
    
    def add_files(self):
        """Add files via dialog."""
        filetypes = [
            ("All Office Files", " ".join(f"*{ext}" for ext in ALL_EXTENSIONS)),
            ("Excel Files", "*.xlsx *.xls *.xlsm *.xlsb"),
            ("Word Files", "*.docx *.doc *.docm *.rtf"),
            ("PowerPoint Files", "*.pptx *.ppt *.pptm *.ppsx"),
            ("All Files", "*.*")
        ]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        for f in files:
            if f not in self.file_list:
                self.file_list.append(f)
        self._refresh_listbox()
        self._update_status()
    
    def add_folder(self):
        """Add all Office files from folder."""
        folder = filedialog.askdirectory()
        if folder:
            count = 0
            for f in os.listdir(folder):
                ext = os.path.splitext(f)[1].lower()
                if ext in ALL_EXTENSIONS:
                    full_path = os.path.join(folder, f)
                    if full_path not in self.file_list:
                        self.file_list.append(full_path)
                        count += 1
            self.log(f"Added {count} files from folder")
            self._refresh_listbox()
            self._update_status()
    
    def _refresh_listbox(self):
        """Refresh listbox with numbered file list and completion status."""
        self.listbox.delete(0, "end")
        for i, file_path in enumerate(self.file_list, 1):
            file_name = os.path.basename(file_path)
            if file_path in self.completed_files:
                display = f"✅ {i}. {file_name}"
            else:
                display = f"    {i}. {file_name}"
            self.listbox.insert("end", display)
    
    def clear_list(self):
        """Clear file list."""
        self.file_list.clear()
        self.completed_files.clear()
        self.listbox.delete(0, "end")
        self._update_status()
    
    def delete_selected(self):
        """Delete selected files."""
        selected = list(self.listbox.curselection())
        for i in reversed(selected):
            del self.file_list[i]
        self._refresh_listbox()
        self._update_status()
    
    def select_output_folder(self):
        """Select output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.lbl_output.config(text=folder, foreground="blue")
            self.config.set("output_folder", folder)
    
    def reset_output_folder(self):
        """Reset to default output."""
        self.output_folder = ""
        self.lbl_output.config(text=get_text("output_default", self.current_lang), foreground="gray")
        self.config.set("output_folder", "")
    
    def _update_status(self):
        """Update status label and estimated time."""
        count = len(self.file_list)
        self.lbl_status.config(text=get_text("file_count", self.current_lang).format(count))
        self._update_estimated_time()
    
    def _update_estimated_time(self):
        """Calculate and display total estimated conversion time."""
        if not self.file_list:
            self.lbl_estimated_time.config(text="")
            return
        
        # Calculate total estimated time for all files
        total_seconds = 0
        for file_path in self.file_list:
            try:
                total_seconds += estimate_conversion_time(file_path)
            except Exception:
                total_seconds += 10  # Default fallback
        
        # Format with translations
        minutes = int(total_seconds // 60)
        seconds = int(total_seconds % 60)
        
        est_label = get_text("estimated_time", self.current_lang)
        min_text = get_text("minute", self.current_lang)
        sec_text = get_text("second", self.current_lang)
        
        if minutes > 0:
            time_text = f"{est_label} ⏱️ ~{minutes} {min_text} {seconds} {sec_text}"
        else:
            time_text = f"{est_label} ⏱️ ~{seconds} {sec_text}"
        
        self.lbl_estimated_time.config(text=time_text)
    
    def _on_language_change(self, event):
        """Handle language change - refresh entire UI."""
        selected_name = self.combo_lang.get()
        for code, data in LANGUAGES.items():
            if data["name"] == selected_name:
                self.current_lang = code
                set_language(code)
                self.config.language = code
                self.config.save()
                self._refresh_ui_language()
                break
    
    def _refresh_ui_language(self):
        """Refresh all UI text to current language."""
        lang = self.current_lang
        
        # Window title
        self.root.title(f"{get_text('app_title', lang)} - v{__version__}")
        
        # File list frame
        self.frame_files.config(text=get_text("file_list_title", lang))
        
        # Buttons row 1
        self.btn_add.config(text=get_text("btn_add_file", lang))
        self.btn_folder.config(text=get_text("btn_add_folder", lang))
        self.btn_clear.config(text=get_text("btn_clear", lang))
        self.btn_convert.config(text=get_text("btn_convert", lang))
        
        # Theme button
        if self.current_theme == "dark":
            self.btn_theme.config(text=get_text("btn_light", lang))
        else:
            self.btn_theme.config(text=get_text("btn_dark", lang))
        
        # PDF Tools row
        self.lbl_pdf_tools.config(text=get_text("pdf_tools", lang))
        self.btn_merge.config(text=get_text("btn_merge", lang))
        self.btn_split.config(text=get_text("btn_split", lang))
        
        # Output folder
        self.lbl_output_title.config(text=get_text("output_folder", lang))
        self.btn_select.config(text=get_text("btn_select", lang))
        self.btn_reset.config(text=get_text("btn_reset", lang))
        if not self.output_folder:
            self.lbl_output.config(text=get_text("output_default", lang))
        
        # PDF Options frame
        self.frame_options.config(text=get_text("options_title", lang))
        self.rb_all_sheets.config(text=get_text("all_sheets", lang))
        self.rb_specific.config(text=get_text("specific_sheets", lang))
        self.lbl_sheet_hint.config(text=get_text("sheet_hint", lang))
        
        # Quality
        self.lbl_quality.config(text=get_text("quality_label", lang))
        self.rb_quality_high.config(text=get_text("quality_high", lang))
        self.rb_quality_min.config(text=get_text("quality_min", lang))
        
        # Scan mode checkbox
        if hasattr(self, 'chk_scan'):
            self.chk_scan.config(text=get_text("scan_mode", lang))
        
        # Security frame
        self.frame_security.config(text=get_text("security_label", lang))
        self.chk_password.config(text=get_text("password_label", lang))
        
        # Author/Title/Page labels
        self.lbl_author.config(text=get_text("author_label", lang))
        self.lbl_title.config(text=get_text("title_label", lang))
        self.lbl_page_range.config(text=get_text("page_range", lang))
        self.lbl_page_hint.config(text=get_text("page_hint", lang))
        
        # Progress frame
        self.frame_progress.config(text=get_text("progress_title", lang))
        self._update_estimated_time()  # Refresh estimated time with new language
        # Clear elapsed/remaining (they update during conversion)
        self.lbl_elapsed_time.config(text="")
        self.lbl_remaining_time.config(text="")
        
        # Log frame
        self.frame_log.config(text=get_text("log_title", lang))
        
        # Status label
        self._update_status()
        
        # Log the change
        self.log(f"🌐 {get_text('language', lang)} → {LANGUAGES[lang]['name']}")
    
    # === PDF TOOLS ===
    
    def merge_pdfs(self):
        """Merge PDF files."""
        files = filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        if len(files) < 2:
            messagebox.showwarning("Warning", "Select at least 2 PDF files to merge")
            return
        
        output = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if output:
            result = merge_pdfs(list(files), output)
            if result is True:
                messagebox.showinfo("Success", f"Merged to: {output}")
            else:
                messagebox.showerror("Error", str(result))
    
    def split_pdf(self):
        """Split PDF file into pages."""
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            count, error = split_pdf(file, folder)
            if error:
                messagebox.showerror("Error", error)
            else:
                messagebox.showinfo("Success", f"Split into {count} files")
    
    def compress_pdf(self):
        """Compress PDF files (batch support)."""
        from office_converter.core.pdf_tools import compress_pdf as do_compress
        
        files = filedialog.askopenfilenames(filetypes=[("PDF Files", "*.pdf")])
        if not files:
            return
        
        # Ask for output folder
        output_folder = filedialog.askdirectory(title="Select output folder for compressed files")
        if not output_folder:
            return
        
        # Compress all files
        total_orig = 0
        total_new = 0
        success_count = 0
        
        for file in files:
            base_name = os.path.splitext(os.path.basename(file))[0]
            output = os.path.join(output_folder, f"{base_name}_compressed.pdf")
            
            orig_size = os.path.getsize(file)
            success, ratio = do_compress(file, output, quality="medium")
            
            if success:
                new_size = os.path.getsize(output)
                total_orig += orig_size
                total_new += new_size
                success_count += 1
                self.log(f"✅ {base_name}: {orig_size/1024:.0f}KB → {new_size/1024:.0f}KB")
        
        # Summary
        if success_count > 0:
            total_ratio = (1 - total_new / total_orig) * 100 if total_orig > 0 else 0
            messagebox.showinfo("Success", 
                f"Compressed {success_count}/{len(files)} files\n"
                f"{total_orig/1024:.0f}KB → {total_new/1024:.0f}KB\n"
                f"({total_ratio:.1f}% reduced)")
        else:
            messagebox.showerror("Error", "Compression failed")
    
    def add_watermark(self):
        """Add watermark to PDF."""
        from office_converter.core.pdf_tools import add_watermark as do_watermark
        
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        # Simple dialog for watermark text
        from tkinter import simpledialog
        text = simpledialog.askstring("Watermark", "Enter watermark text:", initialvalue="CONFIDENTIAL")
        if not text:
            return
        
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=os.path.splitext(os.path.basename(file))[0] + "_watermarked.pdf"
        )
        if output:
            success = do_watermark(file, output, text, opacity=0.3)
            if success:
                messagebox.showinfo("Success", f"Watermark added: {text}")
            else:
                messagebox.showerror("Error", "Failed to add watermark")
    
    def pdf_to_images(self):
        """Convert PDF to images."""
        from office_converter.core.pdf_tools import pdf_to_images as do_pdf_to_img
        
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        folder = filedialog.askdirectory(title="Select output folder for images")
        if not folder:
            return
        
        try:
            images = do_pdf_to_img(file, folder, dpi=150, image_format="png")
            if images:
                messagebox.showinfo("Success", f"Created {len(images)} images\nFolder: {folder}")
            else:
                messagebox.showerror("Error", f"Conversion failed\nInput: {file}\nOutput: {folder}")
        except Exception as e:
            messagebox.showerror("Error", f"Exception: {str(e)}")
    
    def images_to_pdf(self):
        """Convert images to PDF."""
        from office_converter.core.pdf_tools import images_to_pdf as do_img_to_pdf
        
        files = filedialog.askopenfilenames(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif")]
        )
        if not files:
            return
        
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="combined.pdf"
        )
        if output:
            success = do_img_to_pdf(list(files), output)
            if success:
                messagebox.showinfo("Success", f"Created PDF with {len(files)} images")
            else:
                messagebox.showerror("Error", "Conversion failed")
    
    def rotate_pdf(self):
        """Rotate PDF pages."""
        from office_converter.core.pdf_tools import rotate_pages
        from tkinter import simpledialog
        
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        # Ask for rotation angle
        angle = simpledialog.askinteger(
            "Rotate Pages", 
            "Enter rotation angle:\n90 = Clockwise\n180 = Upside down\n270 = Counter-clockwise",
            initialvalue=90,
            minvalue=90,
            maxvalue=270
        )
        if angle not in [90, 180, 270]:
            messagebox.showerror("Error", "Rotation must be 90, 180, or 270")
            return
        
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=os.path.splitext(os.path.basename(file))[0] + "_rotated.pdf"
        )
        if output:
            success = rotate_pages(file, output, angle)
            if success:
                messagebox.showinfo("Success", f"Rotated pages by {angle}°")
            else:
                messagebox.showerror("Error", "Rotation failed")
    
    def extract_pdf_pages(self):
        """Extract specific pages from PDF."""
        from office_converter.core.pdf_tools import extract_pages
        from tkinter import simpledialog
        
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        # Ask for page range
        page_range = simpledialog.askstring(
            "Extract Pages",
            "Enter page range (1-indexed):\nExamples: 1-5, 7, 10-15",
            initialvalue="1-3"
        )
        if not page_range:
            return
        
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=os.path.splitext(os.path.basename(file))[0] + "_extracted.pdf"
        )
        if output:
            success, count = extract_pages(file, output, page_range)
            if success:
                messagebox.showinfo("Success", f"Extracted {count} pages")
            else:
                messagebox.showerror("Error", "Extraction failed")
    
    def delete_pdf_pages(self):
        """Delete specific pages from PDF."""
        from office_converter.core.pdf_tools import delete_pages
        from tkinter import simpledialog
        
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        # Ask for page range to delete
        page_range = simpledialog.askstring(
            "Delete Pages",
            "Enter pages to DELETE (1-indexed):\nExamples: 1, 3-5, 10",
            initialvalue="1"
        )
        if not page_range:
            return
        
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=os.path.splitext(os.path.basename(file))[0] + "_deleted.pdf"
        )
        if output:
            success, count = delete_pages(file, output, page_range)
            if success:
                messagebox.showinfo("Success", f"Deleted {count} pages")
            else:
                messagebox.showerror("Error", "Deletion failed")
    
    def reverse_pdf(self):
        """Reverse page order in PDF."""
        from office_converter.core.pdf_tools import reverse_pages
        
        file = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not file:
            return
        
        output = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=os.path.splitext(os.path.basename(file))[0] + "_reversed.pdf"
        )
        if output:
            success = reverse_pages(file, output)
            if success:
                messagebox.showinfo("Success", "Page order reversed")
            else:
                messagebox.showerror("Error", "Reverse failed")
    
    def open_pdf_tools_dialog(self):
        """Open unified PDF Tools dialog."""
        from office_converter.ui.pdf_tools_dialog import show_pdf_tools_dialog
        show_pdf_tools_dialog(self.root, self.current_lang)
    
    # === UX ENHANCEMENTS ===
    
    def show_settings(self):
        """Show settings dialog."""
        def on_save():
            # Refresh UI after settings change
            self._apply_theme()
            self.root.title(f"{get_text('app_title', self.config.language)} - v{__version__}")
        
        show_settings(self.root, self.config, self.current_lang, on_save)
    
    def show_history(self):
        """Show conversion history dialog."""
        history = get_history()
        stats = history.get_stats()
        records = history.get_recent(30)
        
        dialog = tk.Toplevel(self.root)
        dialog.title("📊 Conversion History")
        dialog.geometry("550x450")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Stats frame
        frame_stats = ttk.LabelFrame(dialog, text="Statistics", padding=5)
        frame_stats.pack(fill="x", padx=10, pady=5)
        
        stats_text = f"Total: {stats['total']} | Success: {stats['success']} | Failed: {stats['failed']} | Rate: {stats['success_rate']} | Avg: {stats['avg_duration']}s"
        ttk.Label(frame_stats, text=stats_text).pack(anchor="w")
        
        # Records list
        frame_list = ttk.LabelFrame(dialog, text="Recent Conversions", padding=5)
        frame_list.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Treeview for records
        columns = ("time", "file", "type", "status", "duration")
        tree = ttk.Treeview(frame_list, columns=columns, show="headings", height=15)
        
        tree.heading("time", text="Time")
        tree.heading("file", text="File")
        tree.heading("type", text="Type")
        tree.heading("status", text="Status")
        tree.heading("duration", text="Duration")
        
        tree.column("time", width=130)
        tree.column("file", width=200)
        tree.column("type", width=60)
        tree.column("status", width=60)
        tree.column("duration", width=70)
        
        for r in records:
            status_icon = "✅" if r.success else "❌"
            tree.insert("", "end", values=(
                r.timestamp, os.path.basename(r.input_file), 
                r.file_type.upper(), status_icon, f"{r.duration}s"
            ))
        
        tree.pack(fill="both", expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(frame_list, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Buttons
        frame_btns = ttk.Frame(dialog)
        frame_btns.pack(fill="x", padx=10, pady=10)
        
        def clear_history():
            if messagebox.askyesno("Confirm", "Clear all history?"):
                history.clear()
                dialog.destroy()
        
        ttk.Button(frame_btns, text="🗑️ Clear History", command=clear_history).pack(side="left")
        ttk.Button(frame_btns, text="❌ Close", command=dialog.destroy).pack(side="right")
    
    def handle_drop(self, files):
        """Handle drag & drop files."""
        for f in files:
            # Decode bytes if needed
            if isinstance(f, bytes):
                f = f.decode('utf-8')
            
            ext = os.path.splitext(f)[1].lower()
            if ext in ALL_EXTENSIONS and f not in self.file_list:
                self.file_list.append(f)
                self.listbox.insert("end", os.path.basename(f))
        
        self._update_status()
        self.log(f"Dropped {len(files)} files")
    
    # === CONVERSION ===
    
    def start_conversion(self, start_index: int = 0):
        """Start conversion thread."""
        if not self.file_list:
            messagebox.showwarning(get_text("warning_title", self.current_lang),
                                   get_text("empty_list_warning", self.current_lang))
            return
        
        if self.is_converting:
            return
        
        self.is_converting = True
        self.stop_requested = False
        self.btn_convert.config(state="disabled")
        
        # Show Stop button (red emergency style)
        self.btn_stop.config(text=get_text("btn_stop", self.current_lang), style="Emergency.TButton")
        self.btn_stop.pack(side="right", padx=2)
        
        thread = threading.Thread(target=self._run_conversion, args=(start_index,), daemon=True)
        thread.start()
    
    def _toggle_stop_resume(self):
        """Handle Stop/Resume button click."""
        if self.is_converting:
            # STOP: Request stop
            self.stop_requested = True
            self.log("⏹️ Stop requested... waiting for current file to finish")
            self.btn_stop.config(state="disabled")  # Disable while stopping
        else:
            # RESUME: Continue from where we stopped
            if self.stopped_at_index < len(self.file_list):
                self.log(f"▶️ Resuming from file {self.stopped_at_index + 1}/{len(self.file_list)}")
                self.start_conversion(start_index=self.stopped_at_index)
    
    def _on_stop_complete(self, stopped_index: int, total: int):
        """Called when stop is complete. Update UI to show Resume button."""
        self.is_converting = False
        self.stop_requested = False
        
        # Update status
        remaining = total - stopped_index
        self.lbl_status.config(text=f"⏸️ Stopped at {stopped_index}/{total} ({remaining} remaining)", foreground="orange")
        self.log(f"⏹️ Stopped. {remaining} files remaining.")
        
        # Change Stop button to Resume (green style)
        self.btn_stop.config(text=get_text("btn_resume", self.current_lang), 
                            style="Resume.TButton", state="normal")
        self.btn_convert.config(state="normal")
    
    def _run_conversion(self, start_index: int = 0):
        """Conversion worker thread with accurate progress tracking."""
        import pythoncom
        pythoncom.CoInitialize()
        
        total = len(self.file_list)
        completed = start_index  # Start from resume point
        start_time = time.time()
        quality = self.var_quality.get()
        
        # Sheet options (for Excel)
        sheet_indices = None
        if self.var_sheet_option.get() == 1:
            parsed = parse_page_range(self.var_sheet_index.get())
            if parsed:
                sheet_indices = [i + 1 for i in parsed]  # 1-indexed for Excel
        
        # Group files by converter type
        converters = {}
        
        # Calculate total estimated time for all files
        total_estimated_time = sum(estimate_conversion_time(f) for f in self.file_list)
        
        # Time display helper
        def format_time(seconds: float) -> str:
            """Format seconds as Xm Ys."""
            m = int(seconds // 60)
            s = int(seconds % 60)
            if m > 0:
                return f"{m}{get_text('minute', self.current_lang)} {s}{get_text('second', self.current_lang)}"
            return f"{s}{get_text('second', self.current_lang)}"
        
        def update_time_display():
            """Update elapsed and remaining time labels."""
            elapsed = time.time() - start_time
            # Remaining = Estimated - Elapsed (simple formula)
            remaining = max(0, total_estimated_time - elapsed)
            
            elapsed_text = f"{get_text('elapsed_time', self.current_lang)} {format_time(elapsed)}"
            remaining_text = f"{get_text('remaining_time', self.current_lang)} {format_time(remaining)}"
            
            self.root.after(0, lambda: self.lbl_elapsed_time.config(text=elapsed_text))
            self.root.after(0, lambda: self.lbl_remaining_time.config(text=remaining_text))
        
        # Progress helper - runs 0-100% for EACH file
        def update_progress(percent: int):
            """Update progress bar (0-100) for current file."""
            self.root.after(0, lambda p=percent: self.progress_bar.configure(value=p))
            update_time_display()  # Also update time display
        
        try:
            for i, file_path in enumerate(self.file_list):
                # Skip files before start_index (for resume)
                if i < start_index:
                    continue
                
                # Check if stop requested
                if self.stop_requested:
                    self.stopped_at_index = i
                    self.root.after(0, lambda idx=i: self._on_stop_complete(idx, total))
                    return  # Exit conversion loop
                
                file_name = os.path.basename(file_path)
                
                # RESET progress bar to 0% for this file
                update_progress(0)
                time.sleep(0.1)  # Brief pause so user sees reset
                
                msg = f"[{i+1}/{total}] {get_text('processing_log', self.current_lang).format(file_name)}"
                self.root.after(0, lambda m=msg: self.log(m))
                self.root.after(0, lambda m=msg: self.lbl_status.config(text=m))
                update_progress(5)  # 5% - Starting
                
                # Get converter
                converter_class = get_converter_for_file(file_path)
                if not converter_class:
                    self.root.after(0, lambda: self.log(f"   ⚠️ Unsupported file type"))
                    update_progress(100)  # Skip this file
                    continue
                
                # Reuse or create converter
                if converter_class not in converters:
                    converters[converter_class] = converter_class(
                        log_callback=lambda m: self.root.after(0, lambda m=m: self.log(f"   {m}"))
                    )
                    converters[converter_class].initialize()
                
                converter = converters[converter_class]
                update_progress(15)  # 15% - Converter ready
                
                # Output path
                if self.output_folder:
                    pdf_path = os.path.join(self.output_folder, os.path.splitext(file_name)[0] + ".pdf")
                else:
                    pdf_path = os.path.splitext(file_path)[0] + ".pdf"
                
                # Phase 2: Converting (0-90%) - progress runs during estimated time
                update_progress(0)  # Reset to 0%
                
                # Estimate conversion time based on file size and system specs
                estimated_time = estimate_conversion_time(file_path)
                
                # Smart animation thread - progress runs from 0% to 90% over estimated time
                converting_done = threading.Event()
                def animate_progress():
                    start_percent = 0
                    end_percent = 90  # Stop at 90%, jump to 100% when done
                    range_percent = end_percent - start_percent  # 90%
                    
                    interval = 0.1  # 100ms updates for smooth animation
                    total_steps = estimated_time / interval
                    base_increment = range_percent / total_steps
                    
                    progress = float(start_percent)
                    slowdown = 1.0
                    
                    while not converting_done.is_set() and progress < end_percent:
                        time.sleep(interval)
                        
                        # Asymptotic slowdown when approaching 90%
                        if progress > 70:
                            slowdown = max(0.2, slowdown * 0.97)
                        
                        progress += base_increment * slowdown
                        
                        if progress > end_percent:
                            progress = end_percent
                        
                        update_progress(int(progress))
                
                anim_thread = threading.Thread(target=animate_progress, daemon=True)
                anim_thread.start()
                
                # Track conversion time for this file
                file_start_time = time.time()
                
                try:
                    # Pass sheet_indices only for Excel
                    if converter_class == ExcelConverter and sheet_indices:
                        success = converter.convert(file_path, pdf_path, quality=quality, sheet_indices=sheet_indices)
                    else:
                        success = converter.convert(file_path, pdf_path, quality=quality)
                    
                    # Calculate actual conversion time
                    file_duration = time.time() - file_start_time
                    
                    converting_done.set()  # Stop animation
                    anim_thread.join(timeout=0.5)
                    
                    if success:
                        # Log conversion for adaptive learning
                        try:
                            log_conversion_result(file_path, file_duration, success=True)
                        except Exception:
                            pass
                        
                        # Post-processing (all done, then jump to 100%)
                        
                        # Page range extraction
                        page_range_str = self.var_page_range.get()
                        page_indices = parse_page_range(page_range_str)
                        if page_indices and HAS_PYMUPDF:
                            if extract_pdf_pages(pdf_path, page_indices):
                                self.root.after(0, lambda pr=page_range_str: self.log(
                                    f"   {get_text('extracting_pages', self.current_lang).format(pr)}"))
                        
                        # Password and metadata
                        password = self.var_password.get() if self.var_password_enabled.get() else None
                        author = self.var_author.get()
                        title = self.var_title.get()
                        
                        if HAS_PYMUPDF and (password or author or title):
                            post_process_pdf(pdf_path, password=password, author=author, title=title)
                            if password:
                                self.root.after(0, lambda: self.log(f"   {get_text('password_set', self.current_lang)}"))
                        
                        # Scan mode
                        if self.var_scan_mode.get() and HAS_PYMUPDF:
                            rasterize_pdf(pdf_path)
                            self.root.after(0, lambda: self.log(f"   {get_text('scan_switched', self.current_lang)}"))
                        
                        # JUMP TO 100% - FILE COMPLETE!
                        update_progress(100)
                        self.root.after(0, lambda: self.log(f"   {get_text('complete_log', self.current_lang)}"))
                        
                        # Mark file as completed and refresh listbox with tick
                        self.completed_files.add(file_path)
                        self.root.after(0, self._refresh_listbox)
                        
                        completed += 1
                    else:
                        # Log failed conversion
                        try:
                            log_conversion_result(file_path, file_duration, success=False)
                        except Exception:
                            pass
                        self.root.after(0, lambda: self.log(f"   ❌ Conversion failed"))
                        update_progress(100)  # Move to next file
                        
                except Exception as e:
                    self.root.after(0, lambda e=e: self.log(f"   ❌ Error: {str(e)[:50]}"))
                    update_progress(100)  # Move to next file
            
            # Cleanup converters
            for conv in converters.values():
                conv.cleanup()
            
            # Done
            total_time = round(time.time() - start_time, 2)
            self.root.after(0, lambda: self.progress_bar.configure(value=100))
            self.root.after(0, lambda: self.lbl_status.config(
                text=f"{get_text('all_done', self.current_lang)} ({completed}/{total})",
                foreground="green"))
            self.root.after(0, lambda: self.log(
                f"\n{get_text('all_done', self.current_lang)} {get_text('total_time', self.current_lang).format(total_time)}"))
            
            # Show completion dialog
            self.root.after(0, lambda: self._show_completion(completed, total, total_time))
            
        except Exception as e:
            self.root.after(0, lambda e=e: messagebox.showerror("Error", str(e)))
        finally:
            self.is_converting = False
            self.stopped_at_index = 0  # Reset for next conversion
            self.root.after(0, lambda: self.btn_convert.config(state="normal"))
            self.root.after(0, lambda: self.btn_stop.pack_forget())  # Hide Stop button
    
    def _show_completion(self, completed: int, total: int, time_taken: float):
        """Show completion dialog with proper theme colors."""
        # Get current theme colors
        colors = getattr(self, 'colors', {
            'bg_primary': '#FAF9F6',
            'bg_secondary': '#F0EDE5',
            'text_primary': '#1D1C1A',
            'accent': '#1A73E8',
            'success': '#188038'
        })
        
        dialog = tk.Toplevel(self.root)
        dialog.title(get_text("complete_title", self.current_lang))
        dialog.geometry("400x240")
        dialog.resizable(False, False)
        
        # Apply theme background
        dialog.configure(bg=colors['bg_primary'])
        
        # Center on screen
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 400) // 2
        y = (dialog.winfo_screenheight() - 240) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Ensure dialog is visible and on top
        dialog.lift()
        dialog.attributes('-topmost', True)
        dialog.after(100, lambda: dialog.attributes('-topmost', False))  # Remove topmost after showing
        dialog.focus_force()
        
        # Handle close button
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        
        # Main content frame
        content = tk.Frame(dialog, bg=colors['bg_primary'])
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Success message
        tk.Label(content, text=get_text("complete_msg", self.current_lang),
                 font=("Segoe UI", 16, "bold"),
                 bg=colors['bg_primary'],
                 fg=colors.get('success', '#188038')).pack(pady=(10, 5))
        
        # File count
        tk.Label(content, text=f"{completed}/{total} files",
                 font=("Segoe UI", 12),
                 bg=colors['bg_primary'],
                 fg=colors['text_primary']).pack()
        
        # Time
        tk.Label(content, text=get_text("total_time", self.current_lang).format(time_taken),
                 font=("Segoe UI", 10),
                 bg=colors['bg_primary'],
                 fg=colors.get('text_secondary', '#6B6966')).pack(pady=5)
        
        # Gift message - use accent color for visibility
        gift_color = colors.get('accent', '#1A73E8')
        tk.Label(content, text=get_text("gift_msg", self.current_lang),
                 font=("Segoe UI", 9),
                 bg=colors['bg_primary'],
                 fg=gift_color).pack(pady=8)
        
        # Buttons frame
        btn_frame = tk.Frame(content, bg=colors['bg_primary'])
        btn_frame.pack(pady=10)
        
        def open_folder():
            folder = self.output_folder or (os.path.dirname(self.file_list[0]) if self.file_list else "")
            if folder:
                os.startfile(folder)
        
        ttk.Button(btn_frame, text=get_text("btn_open_folder", self.current_lang),
                   command=open_folder).pack(side="left", padx=5)
        ttk.Button(btn_frame, text=get_text("btn_exit", self.current_lang),
                   command=dialog.destroy).pack(side="left", padx=5)


def main():
    """Main entry point."""
    setup_logging()
    
    root = tk.Tk()
    app = ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

