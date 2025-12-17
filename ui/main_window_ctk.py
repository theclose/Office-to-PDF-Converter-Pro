"""
Office Converter - Modern UI with CustomTkinter
Version 3.0.0 - Complete UI redesign with improved UX
"""

import os
import sys
import time
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import List, Optional

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

# Supported file extensions
ALL_EXTENSIONS = [".xlsx", ".xls", ".xlsm", ".xlsb", ".docx", ".doc", ".docm", ".rtf", 
                  ".pptx", ".ppt", ".pptm", ".ppsx", ".pps"]

# CustomTkinter settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ModernConverterApp(ctk.CTk):
    """Modern Office to PDF Converter with improved UX."""
    
    def __init__(self):
        super().__init__()
        
        # Config
        self.config = Config()
        self.current_lang = self.config.language
        
        # State
        self.file_list: List[str] = []
        self.completed_files: set = set()
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
        self.geometry("750x700")
        self.minsize(700, 650)
        
        # Center window
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 750) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"750x700+{x}+{y}")
        
        # Build UI
        self._create_widgets()
        
        # Keyboard shortcuts
        self.bind('<Control-o>', lambda e: self.add_files())
        self.bind('<Delete>', lambda e: self.delete_selected())
        self.bind('<Return>', lambda e: self.start_conversion() if not self.is_converting else None)
        
        # Cleanup on exit
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _create_widgets(self):
        """Create all UI widgets with modern layout."""
        
        # === HEADER ===
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(15, 5))
        
        title_label = ctk.CTkLabel(header, text="📄 Office to PDF Converter", 
                                   font=ctk.CTkFont(size=24, weight="bold"))
        title_label.pack(side="left")
        
        # Theme toggle
        self.theme_switch = ctk.CTkSwitch(header, text="🌙", command=self._toggle_theme,
                                          width=50, onvalue="dark", offvalue="light")
        self.theme_switch.pack(side="right", padx=10)
        if ctk.get_appearance_mode() == "Dark":
            self.theme_switch.select()
        
        # === MAIN CONTENT ===
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # === DROP ZONE / FILE LIST ===
        self.file_frame = ctk.CTkFrame(main_frame, corner_radius=15)
        self.file_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        # Drop zone label (shown when empty)
        self.drop_label = ctk.CTkLabel(
            self.file_frame, 
            text="📁 Kéo thả files vào đây\nhoặc click nút bên dưới",
            font=ctk.CTkFont(size=16),
            text_color="gray"
        )
        self.drop_label.pack(expand=True, pady=40)
        
        # File listbox (hidden initially, shown when files added)
        self.file_textbox = ctk.CTkTextbox(self.file_frame, height=200, font=ctk.CTkFont(size=13))
        
        # File action buttons
        file_btn_frame = ctk.CTkFrame(self.file_frame, fg_color="transparent")
        file_btn_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_add = ctk.CTkButton(file_btn_frame, text="➕ Thêm Files", 
                                      command=self.add_files, width=120)
        self.btn_add.pack(side="left", padx=5)
        
        self.btn_folder = ctk.CTkButton(file_btn_frame, text="📁 Thêm Folder", 
                                         command=self.add_folder, width=120,
                                         fg_color="transparent", border_width=2)
        self.btn_folder.pack(side="left", padx=5)
        
        self.btn_clear = ctk.CTkButton(file_btn_frame, text="🗑️ Xóa", 
                                        command=self.clear_list, width=80,
                                        fg_color="transparent", border_width=2,
                                        hover_color="#DC2626")
        self.btn_clear.pack(side="left", padx=5)
        
        # File count label
        self.file_count_label = ctk.CTkLabel(file_btn_frame, text="0 files", 
                                              text_color="gray")
        self.file_count_label.pack(side="right", padx=10)
        
        # === CONVERT BUTTON (HERO) ===
        self.btn_convert = ctk.CTkButton(
            main_frame, 
            text="🚀 CHUYỂN ĐỔI SANG PDF",
            command=self.start_conversion,
            height=50,
            font=ctk.CTkFont(size=18, weight="bold"),
            fg_color="#16A34A",
            hover_color="#15803D"
        )
        self.btn_convert.pack(fill="x", pady=10)
        
        # Progress bar (hidden initially)
        self.progress_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=20)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(self.progress_frame, text="", 
                                           font=ctk.CTkFont(size=12))
        self.progress_label.pack()
        
        # Stop button (hidden initially)
        self.btn_stop = ctk.CTkButton(
            self.progress_frame,
            text="⏹️ DỪNG",
            command=self._stop_conversion,
            fg_color="#DC2626",
            hover_color="#B91C1C",
            height=35
        )
        
        # === OPTIONS (Collapsible) ===
        self.options_expanded = False
        
        options_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        options_header.pack(fill="x", pady=(10, 0))
        
        self.btn_options = ctk.CTkButton(
            options_header, 
            text="⚙️ Tùy chọn nâng cao ▼",
            command=self._toggle_options,
            fg_color="transparent",
            text_color=("gray40", "gray60"),
            hover_color=("gray90", "gray20"),
            anchor="w"
        )
        self.btn_options.pack(side="left")
        
        # Output folder (always visible)
        output_frame = ctk.CTkFrame(options_header, fg_color="transparent")
        output_frame.pack(side="right")
        
        ctk.CTkLabel(output_frame, text="📂", font=ctk.CTkFont(size=14)).pack(side="left")
        self.output_label = ctk.CTkLabel(output_frame, text="Cùng folder gốc", 
                                          text_color="gray", font=ctk.CTkFont(size=12))
        self.output_label.pack(side="left", padx=5)
        
        ctk.CTkButton(output_frame, text="Đổi", width=50, height=25,
                      command=self.select_output_folder,
                      fg_color="transparent", border_width=1).pack(side="left")
        
        # Options panel (hidden by default)
        self.options_panel = ctk.CTkFrame(main_frame, corner_radius=10)
        
        # Quality row
        quality_frame = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        quality_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(quality_frame, text="Chất lượng:").pack(side="left")
        ctk.CTkRadioButton(quality_frame, text="Cao", variable=self.var_quality, 
                          value=0).pack(side="left", padx=10)
        ctk.CTkRadioButton(quality_frame, text="Nhỏ gọn", variable=self.var_quality, 
                          value=1).pack(side="left")
        
        ctk.CTkSwitch(quality_frame, text="Scan Mode 📷", variable=self.var_scan_mode,
                     onvalue=True, offvalue=False).pack(side="right")
        
        # Sheet selection (Excel only)
        sheet_frame = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        sheet_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(sheet_frame, text="Excel Sheets:").pack(side="left")
        ctk.CTkRadioButton(sheet_frame, text="Tất cả", variable=self.var_sheet_option, 
                          value=0).pack(side="left", padx=10)
        ctk.CTkRadioButton(sheet_frame, text="Chỉ định:", variable=self.var_sheet_option, 
                          value=1).pack(side="left")
        ctk.CTkEntry(sheet_frame, textvariable=self.var_sheet_index, width=80,
                    placeholder_text="1-3, 5").pack(side="left", padx=5)
        
        # Security row
        security_frame = ctk.CTkFrame(self.options_panel, fg_color="transparent")
        security_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkSwitch(security_frame, text="🔒 Mật khẩu:", variable=self.var_password_enabled,
                     onvalue=True, offvalue=False).pack(side="left")
        self.password_entry = ctk.CTkEntry(security_frame, textvariable=self.var_password, 
                                           show="*", width=120, placeholder_text="Nhập mật khẩu")
        self.password_entry.pack(side="left", padx=10)
        
        ctk.CTkLabel(security_frame, text="Trang:").pack(side="left", padx=(20, 5))
        ctk.CTkEntry(security_frame, textvariable=self.var_page_range, width=100,
                    placeholder_text="1-3, 5, 7").pack(side="left")
        
        # === LOG ===
        log_frame = ctk.CTkFrame(main_frame, corner_radius=10)
        log_frame.pack(fill="both", expand=True, pady=(10, 0))
        
        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(log_header, text="📋 Log", font=ctk.CTkFont(weight="bold")).pack(side="left")
        
        # PDF Tools button
        self.btn_pdf_tools = ctk.CTkButton(log_header, text="🛠️ PDF Tools", width=100,
                                           command=self.open_pdf_tools)
        self.btn_pdf_tools.pack(side="right", padx=5)
        
        self.log_textbox = ctk.CTkTextbox(log_frame, height=120, font=ctk.CTkFont(size=11))
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Initial log
        self.log("🚀 Office to PDF Converter sẵn sàng!")
        self.log(f"📍 Version {__version__}")
    
    def _toggle_theme(self):
        """Toggle dark/light theme."""
        if self.theme_switch.get() == "dark":
            ctk.set_appearance_mode("dark")
        else:
            ctk.set_appearance_mode("light")
    
    def _toggle_options(self):
        """Toggle options panel visibility."""
        if self.options_expanded:
            self.options_panel.pack_forget()
            self.btn_options.configure(text="⚙️ Tùy chọn nâng cao ▼")
        else:
            self.options_panel.pack(fill="x", pady=(5, 0))
            self.btn_options.configure(text="⚙️ Tùy chọn nâng cao ▲")
        self.options_expanded = not self.options_expanded
    
    def log(self, message: str):
        """Add message to log."""
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        logger.info(message)
    
    def _update_file_display(self):
        """Update file list display."""
        count = len(self.file_list)
        self.file_count_label.configure(text=f"{count} file{'s' if count != 1 else ''}")
        
        if count == 0:
            self.file_textbox.pack_forget()
            self.drop_label.pack(expand=True, pady=40)
        else:
            self.drop_label.pack_forget()
            self.file_textbox.pack(fill="both", expand=True, padx=10, pady=(10, 0))
            
            self.file_textbox.delete("1.0", "end")
            for i, f in enumerate(self.file_list, 1):
                filename = os.path.basename(f)
                icon = "✅" if f in self.completed_files else "📄"
                self.file_textbox.insert("end", f"{icon} {i}. {filename}\n")
    
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
        """Clear file list."""
        self.file_list.clear()
        self.completed_files.clear()
        self._update_file_display()
        self.log("🗑️ Đã xóa danh sách")
    
    def delete_selected(self):
        """Delete selected files - for future implementation."""
        pass
    
    def select_output_folder(self):
        """Select output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.output_label.configure(text=folder[-30:] + "..." if len(folder) > 30 else folder)
            self.config.set("output_folder", folder)
    
    def start_conversion(self):
        """Start conversion process."""
        if not self.file_list:
            messagebox.showwarning("Cảnh báo", "Chưa chọn file nào!")
            return
        
        if self.is_converting:
            return
        
        self.is_converting = True
        self.stop_requested = False
        self.completed_files.clear()
        
        # Show progress
        self.progress_frame.pack(fill="x", pady=5)
        self.btn_stop.pack(pady=5)
        self.btn_convert.configure(state="disabled", text="Đang chuyển đổi...")
        
        # Start conversion thread
        thread = threading.Thread(target=self._run_conversion, daemon=True)
        thread.start()
    
    def _stop_conversion(self):
        """Stop conversion."""
        self.stop_requested = True
        self.log("⏹️ Đang dừng...")
    
    def _run_conversion(self):
        """Conversion worker thread."""
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
                    if isinstance(converter, ExcelConverter) and sheet_indices:
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
                self.after(0, lambda f=filename, err=str(e)[:50]: self.log(f"❌ {f}: {err}"))
            
            # Update progress
            progress = (i + 1) / total
            self.after(0, lambda p=progress: self.progress_bar.set(p))
            
            # Log conversion
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
        """Called when conversion is complete."""
        self.is_converting = False
        self.btn_convert.configure(state="normal", text="🚀 CHUYỂN ĐỔI SANG PDF")
        self.btn_stop.pack_forget()
        
        if self.stop_requested:
            self.progress_label.configure(text=f"Đã dừng: {completed}/{total}")
        else:
            self.progress_label.configure(text=f"Hoàn thành: {completed}/{total} ✅")
            self.log(f"🎉 Hoàn thành {completed}/{total} files!")
            
            if self.config.get("auto_open_folder", True):
                folder = self.output_folder or os.path.dirname(self.file_list[0])
                if messagebox.askyesno("Hoàn thành", f"Đã chuyển đổi {completed}/{total} files!\n\nMở folder?"):
                    os.startfile(folder)
    
    def open_pdf_tools(self):
        """Open PDF Tools dialog."""
        from office_converter.ui.pdf_tools_dialog import PDFToolsDialog
        PDFToolsDialog(self, self.current_lang)
    
    def _on_closing(self):
        """Cleanup on window close."""
        release_pool()
        self.destroy()


def main():
    """Main entry point."""
    app = ModernConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
