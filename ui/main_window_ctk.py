"""
Office Converter - Modern UI with CustomTkinter
Version 3.1.0 - Enhanced UX with animations and context-aware options
Phase 2 + Phase 3: Collapsible panels, context-aware options, animations, microinteractions
"""

import os
import sys
import time
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import List, Optional, Set
from CTkToolTip import CTkToolTip  # type: ignore

# Add parent directories to path for imports
ui_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(ui_dir)
root_dir = os.path.dirname(package_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from office_converter.utils.logging_setup import setup_logging, get_logger
from office_converter.utils.config import Config
from office_converter.utils.localization import get_text, LANGUAGES
from office_converter.utils.pdf_tools import (
    post_process_pdf, rasterize_pdf, parse_page_range, extract_pdf_pages, HAS_PYMUPDF
)
from office_converter.utils.com_pool import release_pool
from office_converter.utils.history import get_history
from office_converter import __version__
from office_converter.utils.progress_estimator import estimate_conversion_time, log_conversion_result
from office_converter.converters import get_converter_for_file, ExcelConverter, WordConverter, PPTConverter

# Setup logging
logger = setup_logging()

# File extensions by type
EXCEL_EXTENSIONS = {".xlsx", ".xls", ".xlsm", ".xlsb"}
WORD_EXTENSIONS = {".docx", ".doc", ".docm", ".rtf"}
PPT_EXTENSIONS = {".pptx", ".ppt", ".pptm", ".ppsx", ".pps"}
ALL_EXTENSIONS = list(EXCEL_EXTENSIONS | WORD_EXTENSIONS | PPT_EXTENSIONS)

# CustomTkinter settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class AnimatedButton(ctk.CTkButton):
    """Button with hover animation effects."""
    
    def __init__(self, *args, pulse: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_fg = kwargs.get("fg_color", "#1f538d")
        self.pulse = pulse
        self._pulse_running = False
        
        # Hover effect
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, event):
        """Scale up slightly on hover."""
        pass  # CustomTkinter handles hover colors natively
    
    def _on_leave(self, event):
        """Reset on leave."""
        pass
    
    def start_pulse(self):
        """Start pulsing animation."""
        if self.pulse and not self._pulse_running:
            self._pulse_running = True
            self._animate_pulse()
    
    def stop_pulse(self):
        """Stop pulsing animation."""
        self._pulse_running = False
    
    def _animate_pulse(self):
        """Pulse animation for attention."""
        if not self._pulse_running:
            return
        # Toggle between colors
        current = self.cget("fg_color")
        if current == self.original_fg:
            self.configure(fg_color="#22C55E")
        else:
            self.configure(fg_color=self.original_fg)
        self.after(800, self._animate_pulse)


class FileTypeIndicator(ctk.CTkFrame):
    """Visual indicator showing file type distribution."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, height=8, corner_radius=4, **kwargs)
        
        self.excel_bar = ctk.CTkFrame(self, fg_color="#217346", corner_radius=2)
        self.word_bar = ctk.CTkFrame(self, fg_color="#2B579A", corner_radius=2)
        self.ppt_bar = ctk.CTkFrame(self, fg_color="#D24726", corner_radius=2)
    
    def update_distribution(self, files: List[str]):
        """Update bars based on file type distribution."""
        if not files:
            self.excel_bar.place_forget()
            self.word_bar.place_forget()
            self.ppt_bar.place_forget()
            return
        
        excel_count = sum(1 for f in files if os.path.splitext(f)[1].lower() in EXCEL_EXTENSIONS)
        word_count = sum(1 for f in files if os.path.splitext(f)[1].lower() in WORD_EXTENSIONS)
        ppt_count = sum(1 for f in files if os.path.splitext(f)[1].lower() in PPT_EXTENSIONS)
        total = len(files)
        
        # Calculate percentages
        x = 0
        if excel_count:
            width = excel_count / total
            self.excel_bar.place(relx=x, rely=0, relwidth=width, relheight=1)
            x += width
        else:
            self.excel_bar.place_forget()
        
        if word_count:
            width = word_count / total
            self.word_bar.place(relx=x, rely=0, relwidth=width, relheight=1)
            x += width
        else:
            self.word_bar.place_forget()
        
        if ppt_count:
            width = ppt_count / total
            self.ppt_bar.place(relx=x, rely=0, relwidth=width, relheight=1)
        else:
            self.ppt_bar.place_forget()


class ModernConverterApp(ctk.CTk):
    """Modern Office to PDF Converter with improved UX - Phase 2 & 3."""
    
    def __init__(self):
        super().__init__()
        
        # Config
        self.config = Config()
        self.current_lang = self.config.language
        
        # State
        self.file_list: List[str] = []
        self.completed_files: Set[str] = set()
        self.is_converting = False
        self.stop_requested = False
        self.stopped_at_index = 0
        self.output_folder = self.config.get("output_folder", "")
        
        # Variables
        self.var_quality = ctk.IntVar(value=self.config.pdf_quality)
        self.var_scan_mode = ctk.BooleanVar(value=self.config.get("scan_mode", False))
        self.var_password = ctk.StringVar()
        self.var_password_enabled = ctk.BooleanVar(value=False)
        self.var_author = ctk.StringVar()
        self.var_title = ctk.StringVar()
        self.var_page_range = ctk.StringVar()
        self.var_sheet_option = ctk.IntVar(value=0)
        self.var_sheet_index = ctk.StringVar(value="1")
        
        # Setup window
        self.title(f"Office to PDF Converter Pro - v{__version__}")
        self.geometry("800x750")
        self.minsize(750, 700)
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 800) // 2
        y = (self.winfo_screenheight() - 750) // 2
        self.geometry(f"800x750+{x}+{y}")
        
        # Build UI
        self._create_widgets()
        
        # Keyboard shortcuts
        self.bind('<Control-o>', lambda e: self.add_files())
        self.bind('<Delete>', lambda e: self.delete_selected())
        self.bind('<Return>', lambda e: self.start_conversion() if not self.is_converting else None)
        self.bind('<Escape>', lambda e: self._stop_conversion() if self.is_converting else None)
        
        # Drag and drop support
        self._setup_drag_drop()
        
        # Cleanup on exit
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # Start entrance animation
        self.after(100, self._entrance_animation)
    
    def _entrance_animation(self):
        """Animate UI elements on startup."""
        self.attributes('-alpha', 0.0)
        self._fade_in(0.0)
    
    def _fade_in(self, alpha: float):
        """Fade in window."""
        if alpha < 1.0:
            alpha += 0.05
            self.attributes('-alpha', alpha)
            self.after(15, lambda: self._fade_in(alpha))
        else:
            self.attributes('-alpha', 1.0)
    
    def _setup_drag_drop(self):
        """Setup drag and drop support."""
        try:
            # TkinterDnD support if available
            pass
        except Exception:
            pass
    
    def _create_widgets(self):
        """Create all UI widgets with modern layout."""
        
        # === HEADER ===
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        
        # App icon and title
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        
        title_label = ctk.CTkLabel(title_frame, text="📄 Office to PDF Converter", 
                                   font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(side="left")
        
        version_label = ctk.CTkLabel(title_frame, text=f"v{__version__}", 
                                      font=ctk.CTkFont(size=12), text_color="gray")
        version_label.pack(side="left", padx=(10, 0), pady=(8, 0))
        
        # Right side controls
        controls_frame = ctk.CTkFrame(header, fg_color="transparent")
        controls_frame.pack(side="right")
        
        # History button
        self.btn_history = ctk.CTkButton(controls_frame, text="📊", width=35, 
                                          command=self._show_history,
                                          fg_color="transparent", border_width=1)
        self.btn_history.pack(side="left", padx=5)
        
        # Settings button  
        self.btn_settings = ctk.CTkButton(controls_frame, text="⚙️", width=35,
                                           command=self._show_settings,
                                           fg_color="transparent", border_width=1)
        self.btn_settings.pack(side="left", padx=5)
        
        # Theme toggle with animation
        self.theme_switch = ctk.CTkSwitch(controls_frame, text="🌙", command=self._toggle_theme,
                                          width=50, onvalue="dark", offvalue="light")
        self.theme_switch.pack(side="left", padx=(15, 0))
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        
        # === MAIN CONTENT ===
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # === DROP ZONE / FILE LIST ===
        self.file_frame = ctk.CTkFrame(self.main_frame, corner_radius=15)
        self.file_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # File type indicator bar
        self.file_type_bar = FileTypeIndicator(self.file_frame, fg_color="gray20")
        self.file_type_bar.pack(fill="x", padx=10, pady=(10, 0))
        
        # Drop zone label (shown when empty)
        self.drop_label = ctk.CTkLabel(
            self.file_frame, 
            text="📁 Kéo thả files vào đây\nhoặc click nút bên dưới\n\n💡 Ctrl+O: Thêm files\n⌫ Delete: Xóa files đã chọn",
            font=ctk.CTkFont(size=16),
            text_color="gray"
        )
        self.drop_label.pack(expand=True, pady=30)
        
        # File listbox with scrollbar
        self.file_textbox = ctk.CTkTextbox(self.file_frame, height=180, 
                                            font=ctk.CTkFont(family="Consolas", size=12))
        
        # File action buttons with tooltips
        file_btn_frame = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        file_btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_add = ctk.CTkButton(file_btn_frame, text="➕ Thêm Files", 
                                      command=self.add_files, width=120,
                                      corner_radius=20)
        self.btn_add.pack(side="left", padx=5)
        
        self.btn_folder = ctk.CTkButton(file_btn_frame, text="📁 Folder", 
                                         command=self.add_folder, width=90,
                                         fg_color="transparent", border_width=2,
                                         corner_radius=20)
        self.btn_folder.pack(side="left", padx=5)
        
        self.btn_clear = ctk.CTkButton(file_btn_frame, text="🗑️", 
                                        command=self.clear_list, width=40,
                                        fg_color="transparent", border_width=2,
                                        hover_color="#DC2626", corner_radius=20)
        self.btn_clear.pack(side="left", padx=5)
        
        # File count with type breakdown
        self.file_stats_frame = ctk.CTkFrame(file_btn_frame, fg_color="transparent")
        self.file_stats_frame.pack(side="right", padx=10)
        
        self.file_count_label = ctk.CTkLabel(self.file_stats_frame, text="0 files", 
                                              font=ctk.CTkFont(size=12, weight="bold"))
        self.file_count_label.pack(side="left")
        
        self.file_types_label = ctk.CTkLabel(self.file_stats_frame, text="", 
                                              text_color="gray", font=ctk.CTkFont(size=10))
        self.file_types_label.pack(side="left", padx=(5, 0))
        
        # === CONVERT BUTTON (HERO) with animation ===
        self.btn_convert = AnimatedButton(
            self.main_frame, 
            text="🚀 CHUYỂN ĐỔI SANG PDF",
            command=self.start_conversion,
            height=55,
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color="#16A34A",
            hover_color="#15803D",
            corner_radius=15,
            pulse=True
        )
        self.btn_convert.pack(fill="x", pady=10)
        
        # Progress section (hidden initially)
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        
        # Progress info row
        progress_info = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        progress_info.pack(fill="x")
        
        self.progress_label = ctk.CTkLabel(progress_info, text="", 
                                           font=ctk.CTkFont(size=13))
        self.progress_label.pack(side="left")
        
        self.progress_percent = ctk.CTkLabel(progress_info, text="0%", 
                                              font=ctk.CTkFont(size=13, weight="bold"),
                                              text_color="#22C55E")
        self.progress_percent.pack(side="right")
        
        # Progress bar with gradient effect
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=25, 
                                                corner_radius=10,
                                                progress_color="#22C55E")
        self.progress_bar.pack(fill="x", pady=(5, 10))
        self.progress_bar.set(0)
        
        # Control buttons during conversion
        conversion_btns = ctk.CTkFrame(self.progress_frame, fg_color="transparent")
        conversion_btns.pack(fill="x")
        
        self.btn_stop = ctk.CTkButton(
            conversion_btns,
            text="⏹️ DỪNG",
            command=self._stop_conversion,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            height=40,
            width=150,
            corner_radius=10
        )
        self.btn_stop.pack(side="left")
        
        self.time_label = ctk.CTkLabel(conversion_btns, text="", text_color="gray")
        self.time_label.pack(side="right")
        
        # === CONTEXT-AWARE OPTIONS ===
        self.options_expanded = False
        
        options_header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        options_header.pack(fill="x", pady=(10, 0))
        
        self.btn_options = ctk.CTkButton(
            options_header, 
            text="⚙️ Tùy chọn ▼",
            command=self._toggle_options,
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            anchor="w",
            width=120
        )
        self.btn_options.pack(side="left")
        
        # Context badges (show what options are active)
        self.context_badges = ctk.CTkFrame(options_header, fg_color="transparent")
        self.context_badges.pack(side="left", padx=10)
        
        # Output folder
        output_frame = ctk.CTkFrame(options_header, fg_color="transparent")
        output_frame.pack(side="right")
        
        self.output_icon = ctk.CTkLabel(output_frame, text="📂", font=ctk.CTkFont(size=14))
        self.output_icon.pack(side="left")
        
        self.output_label = ctk.CTkLabel(output_frame, text="Cùng folder gốc", 
                                          text_color="gray", font=ctk.CTkFont(size=12))
        self.output_label.pack(side="left", padx=5)
        
        self.btn_output = ctk.CTkButton(output_frame, text="Đổi", width=50, height=25,
                                         command=self.select_output_folder,
                                         fg_color="transparent", border_width=1,
                                         corner_radius=8)
        self.btn_output.pack(side="left")
        
        # Options panel (hidden by default)
        self.options_panel = ctk.CTkFrame(self.main_frame, corner_radius=12)
        
        # === Quality Section ===
        quality_section = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        quality_section.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkLabel(quality_section, text="📊 Chất lượng", 
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        quality_btns = ctk.CTkFrame(quality_section, fg_color="transparent")
        quality_btns.pack(side="left", padx=20)
        
        self.rb_high = ctk.CTkRadioButton(quality_btns, text="Cao", 
                                           variable=self.var_quality, value=0)
        self.rb_high.pack(side="left", padx=10)
        
        self.rb_min = ctk.CTkRadioButton(quality_btns, text="Nhỏ gọn", 
                                          variable=self.var_quality, value=1)
        self.rb_min.pack(side="left")
        
        # Scan mode
        self.scan_switch = ctk.CTkSwitch(quality_section, text="📷 Scan Mode", 
                                          variable=self.var_scan_mode,
                                          onvalue=True, offvalue=False)
        self.scan_switch.pack(side="right")
        
        # === Excel Sheet Section (Context-aware - only shown when Excel files present) ===
        self.sheet_section = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        
        sheet_header = ctk.CTkFrame(self.sheet_section, fg_color="transparent")
        sheet_header.pack(fill="x")
        
        ctk.CTkLabel(sheet_header, text="📗 Excel Sheets", 
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        self.excel_count_label = ctk.CTkLabel(sheet_header, text="", 
                                               text_color="#217346", 
                                               font=ctk.CTkFont(size=11))
        self.excel_count_label.pack(side="left", padx=10)
        
        sheet_controls = ctk.CTkFrame(self.sheet_section, fg_color="transparent")
        sheet_controls.pack(fill="x", pady=(5, 0))
        
        ctk.CTkRadioButton(sheet_controls, text="Tất cả sheets", 
                          variable=self.var_sheet_option, value=0).pack(side="left", padx=10)
        ctk.CTkRadioButton(sheet_controls, text="Chỉ định:", 
                          variable=self.var_sheet_option, value=1).pack(side="left", padx=10)
        
        self.sheet_entry = ctk.CTkEntry(sheet_controls, textvariable=self.var_sheet_index, 
                                         width=100, placeholder_text="1-3, 5")
        self.sheet_entry.pack(side="left", padx=5)
        
        ctk.CTkLabel(sheet_controls, text="(ví dụ: 1-3, 5, 7)", 
                    text_color="gray", font=ctk.CTkFont(size=10)).pack(side="left", padx=5)
        
        # === Security Section ===
        security_section = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        security_section.pack(fill="x", padx=15, pady=12)
        
        ctk.CTkLabel(security_section, text="🔒 Bảo mật", 
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        security_controls = ctk.CTkFrame(security_section, fg_color="transparent")
        security_controls.pack(side="left", padx=20)
        
        self.pw_switch = ctk.CTkSwitch(security_controls, text="Mật khẩu:", 
                                        variable=self.var_password_enabled,
                                        onvalue=True, offvalue=False,
                                        command=self._on_password_toggle)
        self.pw_switch.pack(side="left")
        
        self.password_entry = ctk.CTkEntry(security_controls, textvariable=self.var_password, 
                                           show="*", width=130, placeholder_text="Nhập mật khẩu",
                                           state="disabled")
        self.password_entry.pack(side="left", padx=10)
        
        # Page range
        ctk.CTkLabel(security_section, text="Trang:", 
                    font=ctk.CTkFont(size=12)).pack(side="right", padx=(0, 5))
        self.page_entry = ctk.CTkEntry(security_section, textvariable=self.var_page_range, 
                                        width=100, placeholder_text="1-3, 5")
        self.page_entry.pack(side="right")
        
        # === LOG ===
        log_frame = ctk.CTkFrame(self.main_frame, corner_radius=12)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=12, pady=(10, 5))
        
        ctk.CTkLabel(log_header, text="📋 Log", 
                    font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        # Clear log button
        ctk.CTkButton(log_header, text="🔄", width=30, height=25,
                     command=self._clear_log,
                     fg_color="transparent", border_width=1).pack(side="left", padx=10)
        
        # PDF Tools button with badge
        self.btn_pdf_tools = ctk.CTkButton(log_header, text="🛠️ PDF Tools", width=110,
                                           command=self.open_pdf_tools,
                                           corner_radius=10)
        self.btn_pdf_tools.pack(side="right", padx=5)
        
        self.log_textbox = ctk.CTkTextbox(log_frame, height=100, 
                                           font=ctk.CTkFont(family="Consolas", size=11))
        self.log_textbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        
        # Initial log
        self.log("🚀 Office to PDF Converter Pro sẵn sàng!")
        self.log(f"📍 Version {__version__} | CustomTkinter UI")
        if HAS_PYMUPDF:
            self.log("✅ PyMuPDF: Hỗ trợ đầy đủ PDF tools")
        else:
            self.log("⚠️ PyMuPDF không có: Một số tính năng bị giới hạn")
    
    def _toggle_theme(self):
        """Toggle dark/light theme with animation."""
        if self.theme_switch.get() == "dark":
            ctk.set_appearance_mode("dark")
            self.theme_switch.configure(text="🌙")
        else:
            ctk.set_appearance_mode("light")
            self.theme_switch.configure(text="☀️")
    
    def _toggle_options(self):
        """Toggle options panel with slide animation."""
        if self.options_expanded:
            self._slide_up_options()
        else:
            self._slide_down_options()
    
    def _slide_down_options(self):
        """Animate options panel sliding down."""
        self.options_panel.pack(fill="x", pady=(5, 0), before=self.main_frame.winfo_children()[-1])
        self.btn_options.configure(text="⚙️ Tùy chọn ▲")
        self.options_expanded = True
        self._update_context_options()
    
    def _slide_up_options(self):
        """Animate options panel sliding up."""
        self.options_panel.pack_forget()
        self.btn_options.configure(text="⚙️ Tùy chọn ▼")
        self.options_expanded = False
    
    def _update_context_options(self):
        """Update options based on file types in list (Context-aware)."""
        # Check for Excel files
        has_excel = any(os.path.splitext(f)[1].lower() in EXCEL_EXTENSIONS 
                       for f in self.file_list)
        
        if has_excel:
            excel_count = sum(1 for f in self.file_list 
                             if os.path.splitext(f)[1].lower() in EXCEL_EXTENSIONS)
            self.sheet_section.pack(fill="x", padx=15, pady=12, after=self.options_panel.winfo_children()[0])
            self.excel_count_label.configure(text=f"({excel_count} file{'s' if excel_count > 1 else ''})")
        else:
            self.sheet_section.pack_forget()
    
    def _on_password_toggle(self):
        """Enable/disable password entry based on switch."""
        if self.var_password_enabled.get():
            self.password_entry.configure(state="normal")
            self.password_entry.focus()
        else:
            self.password_entry.configure(state="disabled")
    
    def _update_context_badges(self):
        """Update context badges showing active options."""
        # Clear existing badges
        for widget in self.context_badges.winfo_children():
            widget.destroy()
        
        badges = []
        
        if self.var_quality.get() == 1:
            badges.append(("📦", "Nhỏ gọn"))
        
        if self.var_scan_mode.get():
            badges.append(("📷", "Scan"))
        
        if self.var_password_enabled.get() and self.var_password.get():
            badges.append(("🔒", ""))
        
        if self.var_page_range.get():
            badges.append(("📄", self.var_page_range.get()))
        
        for icon, text in badges[:3]:  # Max 3 badges
            badge = ctk.CTkLabel(self.context_badges, 
                                text=f"{icon}{text}", 
                                font=ctk.CTkFont(size=10),
                                fg_color=("gray85", "gray25"),
                                corner_radius=8,
                                padx=5, pady=2)
            badge.pack(side="left", padx=2)
    
    def log(self, message: str):
        """Add message to log with timestamp."""
        timestamp = time.strftime("%H:%M:%S")
        self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
        self.log_textbox.see("end")
        logger.info(message)
    
    def _clear_log(self):
        """Clear log textbox."""
        self.log_textbox.delete("1.0", "end")
        self.log("🔄 Log đã được xóa")
    
    def _update_file_display(self):
        """Update file list display with animations."""
        count = len(self.file_list)
        
        # Update file type indicator
        self.file_type_bar.update_distribution(self.file_list)
        
        # Update count label
        self.file_count_label.configure(text=f"{count} file{'s' if count != 1 else ''}")
        
        # Update type breakdown
        excel_count = sum(1 for f in self.file_list if os.path.splitext(f)[1].lower() in EXCEL_EXTENSIONS)
        word_count = sum(1 for f in self.file_list if os.path.splitext(f)[1].lower() in WORD_EXTENSIONS)
        ppt_count = sum(1 for f in self.file_list if os.path.splitext(f)[1].lower() in PPT_EXTENSIONS)
        
        parts = []
        if excel_count: parts.append(f"📗{excel_count}")
        if word_count: parts.append(f"📘{word_count}")
        if ppt_count: parts.append(f"📙{ppt_count}")
        self.file_types_label.configure(text=" ".join(parts))
        
        # Update context options
        if self.options_expanded:
            self._update_context_options()
        
        if count == 0:
            self.file_textbox.pack_forget()
            self.drop_label.pack(expand=True, pady=30)
            self.btn_convert.configure(state="disabled")
        else:
            self.drop_label.pack_forget()
            self.file_textbox.pack(fill="both", expand=True, padx=10, pady=(5, 0))
            self.btn_convert.configure(state="normal")
            
            self.file_textbox.delete("1.0", "end")
            for i, f in enumerate(self.file_list, 1):
                filename = os.path.basename(f)
                ext = os.path.splitext(f)[1].lower()
                
                # Status icon
                if f in self.completed_files:
                    status = "✅"
                else:
                    status = "📗" if ext in EXCEL_EXTENSIONS else "📘" if ext in WORD_EXTENSIONS else "📙"
                
                self.file_textbox.insert("end", f"{status} {i:2d}. {filename}\n")
    
    def add_files(self):
        """Add files via dialog."""
        filetypes = [
            ("All Office Files", " ".join(f"*{ext}" for ext in ALL_EXTENSIONS)),
            ("Excel Files", "*.xlsx *.xls *.xlsm *.xlsb"),
            ("Word Files", "*.docx *.doc *.docm *.rtf"),
            ("PowerPoint Files", "*.pptx *.ppt *.pptm *.ppsx"),
        ]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        added = 0
        for f in files:
            if f not in self.file_list:
                self.file_list.append(f)
                added += 1
        if added:
            self.log(f"➕ Đã thêm {added} file(s)")
        self._update_file_display()
    
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
            self.log(f"📁 Đã thêm {count} file(s) từ folder")
            self._update_file_display()
    
    def clear_list(self):
        """Clear file list with animation."""
        if not self.file_list:
            return
        self.file_list.clear()
        self.completed_files.clear()
        self._update_file_display()
        self.log("🗑️ Đã xóa danh sách")
    
    def delete_selected(self):
        """Delete selected files."""
        pass  # To be implemented with proper text selection
    
    def select_output_folder(self):
        """Select output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            display = folder if len(folder) <= 25 else "..." + folder[-22:]
            self.output_label.configure(text=display, text_color="#22C55E")
            self.config.set("output_folder", folder)
            self.log(f"📂 Output: {folder}")
    
    def start_conversion(self):
        """Start conversion process with animation."""
        if not self.file_list:
            messagebox.showwarning("Cảnh báo", "Chưa chọn file nào!")
            return
        
        if self.is_converting:
            return
        
        self.is_converting = True
        self.stop_requested = False
        self.completed_files.clear()
        self.conversion_start_time = time.time()
        
        # Update badges before conversion
        self._update_context_badges()
        
        # Show progress with animation
        self.progress_frame.pack(fill="x", pady=10, before=self.options_panel if self.options_expanded else self.btn_options.master)
        self.progress_bar.set(0)
        self.progress_percent.configure(text="0%")
        
        self.btn_convert.configure(state="disabled", text="⏳ Đang chuyển đổi...",
                                   fg_color="gray50")
        
        # Start time update thread
        self._update_time_display()
        
        # Start conversion thread
        thread = threading.Thread(target=self._run_conversion, daemon=True)
        thread.start()
    
    def _update_time_display(self):
        """Update elapsed time display."""
        if self.is_converting:
            elapsed = time.time() - self.conversion_start_time
            mins, secs = divmod(int(elapsed), 60)
            self.time_label.configure(text=f"⏱️ {mins:02d}:{secs:02d}")
            self.after(1000, self._update_time_display)
    
    def _stop_conversion(self):
        """Stop conversion."""
        self.stop_requested = True
        self.log("⏹️ Đang dừng...")
        self.btn_stop.configure(state="disabled", text="Đang dừng...")
    
    def _run_conversion(self):
        """Conversion worker thread with progress updates."""
        import pythoncom
        pythoncom.CoInitialize()
        
        total = len(self.file_list)
        completed = 0
        quality = self.var_quality.get()
        
        # Sheet options
        sheet_indices = None
        if self.var_sheet_option.get() == 1:
            parsed = parse_page_range(self.var_sheet_index.get())
            if parsed:
                sheet_indices = [i + 1 for i in parsed]
        
        for i, file_path in enumerate(self.file_list):
            if self.stop_requested:
                self.after(0, lambda: self.log("⏹️ Đã dừng!"))
                break
            
            filename = os.path.basename(file_path)
            self.after(0, lambda f=filename, idx=i+1: self.progress_label.configure(
                text=f"({idx}/{total}) {f}"))
            
            # Determine output path
            if self.output_folder:
                pdf_name = os.path.splitext(filename)[0] + ".pdf"
                pdf_path = os.path.join(self.output_folder, pdf_name)
            else:
                pdf_path = os.path.splitext(file_path)[0] + ".pdf"
            
            start_time = time.time()
            
            try:
                converter = get_converter_for_file(file_path)
                if converter:
                    ext = os.path.splitext(file_path)[1].lower()
                    if isinstance(converter, ExcelConverter) and sheet_indices and ext in EXCEL_EXTENSIONS:
                        success = converter.convert(file_path, pdf_path, quality, sheet_indices)
                    else:
                        success = converter.convert(file_path, pdf_path, quality)
                    converter.cleanup()
                    
                    if success:
                        # Post-processing
                        page_range_str = self.var_page_range.get()
                        page_indices = parse_page_range(page_range_str)
                        if page_indices and HAS_PYMUPDF:
                            extract_pdf_pages(pdf_path, page_indices)
                        
                        password = self.var_password.get() if self.var_password_enabled.get() else None
                        if HAS_PYMUPDF and password:
                            post_process_pdf(pdf_path, password=password)
                        
                        if self.var_scan_mode.get() and HAS_PYMUPDF:
                            rasterize_pdf(pdf_path)
                        
                        self.completed_files.add(file_path)
                        completed += 1
                        self.after(0, lambda f=filename: self.log(f"✅ {f}"))
                        self.after(0, self._update_file_display)
                    else:
                        self.after(0, lambda f=filename: self.log(f"❌ {f}"))
                else:
                    self.after(0, lambda f=filename: self.log(f"❌ Không hỗ trợ: {f}"))
            except Exception as e:
                error_msg = str(e)[:50]
                self.after(0, lambda f=filename, err=error_msg: self.log(f"❌ {f}: {err}"))
            
            # Update progress with smooth animation
            progress = (i + 1) / total
            percent = int(progress * 100)
            self.after(0, lambda p=progress: self.progress_bar.set(p))
            self.after(0, lambda pct=percent: self.progress_percent.configure(text=f"{pct}%"))
            
            # Log conversion time
            duration = time.time() - start_time
            try:
                log_conversion_result(file_path, duration, success=file_path in self.completed_files)
            except Exception:
                pass
        
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        
        # Done
        self.after(0, lambda: self._on_conversion_done(completed, total))
    
    def _on_conversion_done(self, completed: int, total: int):
        """Called when conversion is complete with celebration."""
        self.is_converting = False
        
        # Calculate time
        elapsed = time.time() - self.conversion_start_time
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins}m {secs}s" if mins else f"{secs}s"
        
        # Reset button with animation
        self.btn_convert.configure(
            state="normal", 
            text="🚀 CHUYỂN ĐỔI SANG PDF",
            fg_color="#16A34A"
        )
        self.btn_stop.configure(state="normal", text="⏹️ DỪNG")
        
        if self.stop_requested:
            self.progress_label.configure(text=f"Đã dừng: {completed}/{total}")
            self.log(f"⏸️ Đã dừng sau {completed}/{total} files ({time_str})")
        else:
            self.progress_label.configure(text=f"✅ Hoàn thành: {completed}/{total}")
            self.progress_percent.configure(text="100%", text_color="#22C55E")
            self.log(f"🎉 Hoàn thành {completed}/{total} files trong {time_str}!")
            
            # Success animation
            if completed == total:
                self._success_animation()
            
            # Open folder option
            if self.config.get("auto_open_folder", False):
                folder = self.output_folder or os.path.dirname(self.file_list[0])
                os.startfile(folder)
            elif completed > 0:
                if messagebox.askyesno("🎉 Hoàn thành!", 
                                       f"Đã chuyển đổi {completed}/{total} files\n"
                                       f"Thời gian: {time_str}\n\n"
                                       f"Mở folder chứa PDF?"):
                    folder = self.output_folder or os.path.dirname(self.file_list[0])
                    os.startfile(folder)
    
    def _success_animation(self):
        """Play success animation."""
        # Flash the progress bar green
        self.progress_bar.configure(progress_color="#22C55E")
    
    def open_pdf_tools(self):
        """Open PDF Tools dialog."""
        try:
            from office_converter.ui.pdf_tools_dialog import PDFToolsDialog
            PDFToolsDialog(self, self.current_lang)
        except Exception as e:
            self.log(f"❌ Không thể mở PDF Tools: {e}")
    
    def _show_history(self):
        """Show conversion history."""
        try:
            history = get_history()
            stats = history.get_stats()
            
            dialog = ctk.CTkToplevel(self)
            dialog.title("📊 Lịch sử chuyển đổi")
            dialog.geometry("400x300")
            dialog.transient(self)
            dialog.grab_set()
            
            # Stats display
            stats_text = f"""
📊 THỐNG KÊ TỔNG HỢP

Tổng files đã chuyển đổi: {stats.get('total', 0)}
Thành công: {stats.get('success', 0)}
Thất bại: {stats.get('failed', 0)}
Tỷ lệ thành công: {stats.get('success_rate', 0):.1f}%

Thời gian trung bình: {stats.get('avg_time', 0):.1f}s
            """
            
            text_widget = ctk.CTkTextbox(dialog, font=ctk.CTkFont(size=13))
            text_widget.pack(fill="both", expand=True, padx=15, pady=15)
            text_widget.insert("1.0", stats_text)
            text_widget.configure(state="disabled")
            
            ctk.CTkButton(dialog, text="Đóng", command=dialog.destroy).pack(pady=10)
            
        except Exception as e:
            self.log(f"❌ Lỗi khi mở history: {e}")
    
    def _show_settings(self):
        """Show settings dialog."""
        from office_converter.ui.dialogs import show_settings
        show_settings(self, self.config, self.current_lang, lambda: None)
    
    def _on_closing(self):
        """Cleanup on window close with animation."""
        self.attributes('-alpha', 1.0)
        self._fade_out(1.0)
    
    def _fade_out(self, alpha: float):
        """Fade out window."""
        if alpha > 0:
            alpha -= 0.1
            self.attributes('-alpha', alpha)
            self.after(20, lambda: self._fade_out(alpha))
        else:
            release_pool()
            self.destroy()


def main():
    """Main entry point."""
    app = ModernConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
