"""
Excel Tools Dialog - Modern CustomTkinter interface for Excel operations.

Features:
- Split Excel: Export each sheet as separate file
- Merge Excel: Combine multiple files into one
- Drag & drop support
- Progress tracking
- Background threading
"""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional
import logging
from pathlib import Path

from office_converter.core.excel_tools import (
    split_excel, merge_excel, get_sheet_info, HAS_OPENPYXL,
    excel_to_csv, csv_to_excel, protect_sheets, unprotect_sheets, rename_sheets
)
from office_converter.utils.config import Config

# Drag and drop support
from office_converter.utils.tkdnd_wrapper import HAS_TKDND, DND_FILES
from office_converter.utils.dnd_helpers import parse_dropped_paths

logger = logging.getLogger(__name__)


class ExcelToolsDialog(ctk.CTkToplevel):
    """Modern Excel Tools dialog with CustomTkinter."""
    
    # Operations organized by category
    OPERATIONS = {
        "edit": [
            ("split", "✂️ Tách Sheet", "Xuất mỗi sheet riêng"),
            ("merge", "📎 Gộp Files", "Gộp nhiều file Excel"),
            ("rename", "✏️ Đổi tên Sheet", "Đổi tên hàng loạt"),
        ],
        "convert": [
            ("to_csv", "📄 Excel → CSV", "Xuất sang CSV"),
            ("from_csv", "📊 CSV → Excel", "Nhập từ CSV"),
        ],
        "protect": [
            ("protect", "🔒 Bảo vệ", "Khóa sheets"),
            ("unprotect", "🔓 Mở khóa", "Bỏ bảo vệ sheets"),
        ],
    }
    
    def __init__(self, parent, lang: str = "vi"):
        super().__init__(parent)
        
        self.parent = parent
        self.lang = lang
        self.files: List[str] = []
        self.is_processing = False
        self.stop_requested = False
        
        # Load config
        self.config = Config()
        
        # Window setup
        self.title("📊 Excel Tools")
        self.geometry("900x650")
        self.minsize(800, 550)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 900) // 2
        y = (self.winfo_screenheight() - 650) // 2
        self.geometry(f"+{x}+{y}")
        
        # Variables
        self.var_operation = ctk.StringVar(value="split")
        self.var_merge_mode = ctk.StringVar(value="sheets")
        self.var_skip_header = ctk.BooleanVar(value=True)
        self.var_output_same = ctk.BooleanVar(value=True)
        self.var_output_folder = ctk.StringVar()
        
        # Check openpyxl
        if not HAS_OPENPYXL:
            messagebox.showerror(
                "Thiếu thư viện",
                "Cần cài đặt openpyxl để sử dụng Excel Tools.\n\n"
                "Chạy lệnh: pip install openpyxl"
            )
            self.destroy()
            return
        
        self._create_ui()
        self._setup_drag_drop()
        
        # Window behavior
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Handle window close."""
        self.grab_release()
        self.destroy()
        try:
            if self.parent:
                self.parent.lift()
                self.parent.focus_force()
        except Exception:
            pass
    
    def _create_ui(self):
        """Build the UI."""
        # Main container with 2 columns
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # === LEFT PANEL ===
        left_panel = ctk.CTkFrame(self, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.grid_rowconfigure(3, weight=1)
        
        # Header
        header = ctk.CTkFrame(left_panel, fg_color="#047857", corner_radius=0)
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header,
            text="📊 Excel Tools",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white"
        ).pack(pady=15)
        
        # Operations - Tabbed interface
        self.tab_view = ctk.CTkTabview(left_panel, height=180)
        self.tab_view.pack(fill="x", padx=10, pady=(0, 10))
        
        # Create tabs
        tab_edit = self.tab_view.add("✏️ Chỉnh sửa")
        tab_convert = self.tab_view.add("🔄 Chuyển đổi")
        tab_protect = self.tab_view.add("🔒 Bảo vệ")
        
        # Populate tabs with radio buttons
        for key, label, desc in self.OPERATIONS["edit"]:
            ctk.CTkRadioButton(
                tab_edit, text=f"{label}", variable=self.var_operation,
                value=key, command=self._update_options
            ).pack(anchor="w", padx=10, pady=3)
        
        for key, label, desc in self.OPERATIONS["convert"]:
            ctk.CTkRadioButton(
                tab_convert, text=f"{label}", variable=self.var_operation,
                value=key, command=self._update_options
            ).pack(anchor="w", padx=10, pady=3)
        
        for key, label, desc in self.OPERATIONS["protect"]:
            ctk.CTkRadioButton(
                tab_protect, text=f"{label}", variable=self.var_operation,
                value=key, command=self._update_options
            ).pack(anchor="w", padx=10, pady=3)
        
        # Options panel
        self.options_frame = ctk.CTkFrame(left_panel)
        self.options_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(
            self.options_frame,
            text="🔧 Tùy chọn",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.options_content = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        self.options_content.pack(fill="x", padx=10, pady=(0, 10))
        
        self._update_options()
        
        # Output settings
        output_frame = ctk.CTkFrame(left_panel)
        output_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(
            output_frame,
            text="📂 Thư mục Output",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        ctk.CTkRadioButton(
            output_frame,
            text="Cùng folder với file gốc",
            variable=self.var_output_same,
            value=True
        ).pack(anchor="w", padx=15)
        
        other_row = ctk.CTkFrame(output_frame, fg_color="transparent")
        other_row.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkRadioButton(
            other_row,
            text="Khác:",
            variable=self.var_output_same,
            value=False,
            width=70
        ).pack(side="left")
        
        ctk.CTkEntry(
            other_row,
            textvariable=self.var_output_folder,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            other_row,
            text="📁",
            width=35,
            command=self._browse_output
        ).pack(side="left")
        
        # Action buttons
        action_frame = ctk.CTkFrame(left_panel)
        action_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_process = ctk.CTkButton(
            action_frame,
            text="🚀 THỰC HIỆN",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color="#10B981",
            hover_color="#059669",
            command=self._start_processing
        )
        self.btn_process.pack(fill="x", padx=10, pady=10)
        
        btn_row = ctk.CTkFrame(action_frame, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        
        self.btn_stop = ctk.CTkButton(
            btn_row,
            text="⏹️ Dừng",
            fg_color="#DC2626",
            hover_color="#B91C1C",
            width=100,
            state="disabled",
            command=self._stop_processing
        )
        self.btn_stop.pack(side="left")
        
        ctk.CTkButton(
            btn_row,
            text="Đóng",
            fg_color="#6B7280",
            hover_color="#4B5563",
            width=100,
            command=self._on_close
        ).pack(side="right")
        
        # === RIGHT PANEL ===
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # File list header
        file_header = ctk.CTkFrame(right_panel)
        file_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ctk.CTkLabel(
            file_header,
            text="📁 Danh sách Files Excel",
            font=ctk.CTkFont(weight="bold")
        ).pack(side="left", padx=10, pady=8)
        
        self.lbl_count = ctk.CTkLabel(
            file_header,
            text="0 files",
            text_color="#9CA3AF"
        )
        self.lbl_count.pack(side="right", padx=10)
        
        # File buttons
        btn_frame = ctk.CTkFrame(file_header, fg_color="transparent")
        btn_frame.pack(side="right", padx=5)
        
        for text, cmd in [
            ("➕ Files", self._add_files),
            ("📁 Folder", self._add_folder),
            ("🗑️ Xóa", self._remove_files),
            ("🗑️ Hết", self._clear_files),
        ]:
            ctk.CTkButton(
                btn_frame, text=text, command=cmd,
                width=70, height=28
            ).pack(side="left", padx=2)
        
        # File list
        file_list_frame = ctk.CTkFrame(right_panel)
        file_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        file_list_frame.grid_rowconfigure(0, weight=1)
        file_list_frame.grid_columnconfigure(0, weight=1)
        
        self.file_listbox = tk.Listbox(
            file_list_frame,
            font=("Consolas", 11),
            selectmode=tk.EXTENDED,
            bg="#2b2b2b",
            fg="#dcdcdc",
            selectbackground="#10B981",
            selectforeground="white",
            highlightthickness=0,
            borderwidth=0
        )
        self.file_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Keyboard bindings
        self.file_listbox.bind('<Control-a>', lambda e: self._select_all_files())
        self.file_listbox.bind('<Delete>', lambda e: self._remove_selected())
        
        # Progress section
        progress_frame = ctk.CTkFrame(right_panel)
        progress_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        
        progress_header = ctk.CTkFrame(progress_frame, fg_color="transparent")
        progress_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(
            progress_header,
            text="📊 Tiến trình",
            font=ctk.CTkFont(weight="bold")
        ).pack(side="left")
        
        self.lbl_status = ctk.CTkLabel(
            progress_header,
            text="Sẵn sàng",
            text_color="#9CA3AF"
        )
        self.lbl_status.pack(side="right")
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=20, progress_color="#10B981")
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        # Log section
        log_frame = ctk.CTkFrame(right_panel)
        log_frame.grid(row=3, column=0, sticky="nsew")
        right_panel.grid_rowconfigure(3, weight=1)
        
        ctk.CTkLabel(
            log_frame,
            text="📝 Log",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.log_textbox = ctk.CTkTextbox(
            log_frame,
            height=120,
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _update_options(self):
        """Update options panel based on operation."""
        for widget in self.options_content.winfo_children():
            widget.destroy()
        
        op = self.var_operation.get()
        
        if op == "split":
            ctk.CTkLabel(
                self.options_content,
                text="Xuất tất cả các sheet thành file riêng",
                text_color="#9CA3AF"
            ).pack(anchor="w")
            
        elif op == "merge":
            ctk.CTkLabel(self.options_content, text="Chế độ gộp:").pack(anchor="w")
            
            ctk.CTkRadioButton(
                self.options_content,
                text="Mỗi sheet → 1 sheet trong file kết quả",
                variable=self.var_merge_mode,
                value="sheets"
            ).pack(anchor="w", padx=10)
            
            ctk.CTkRadioButton(
                self.options_content,
                text="Gộp tất cả dữ liệu thành 1 sheet",
                variable=self.var_merge_mode,
                value="rows"
            ).pack(anchor="w", padx=10)
            
            ctk.CTkCheckBox(
                self.options_content,
                text="Bỏ dòng tiêu đề (trừ file đầu)",
                variable=self.var_skip_header
            ).pack(anchor="w", padx=10, pady=(5, 0))
        
        elif op == "rename":
            ctk.CTkLabel(self.options_content, text="Tiền tố (prefix):").pack(anchor="w")
            self.var_prefix = ctk.StringVar()
            ctk.CTkEntry(self.options_content, textvariable=self.var_prefix, width=150).pack(anchor="w", pady=2)
            
            ctk.CTkLabel(self.options_content, text="Hậu tố (suffix):").pack(anchor="w")
            self.var_suffix = ctk.StringVar()
            ctk.CTkEntry(self.options_content, textvariable=self.var_suffix, width=150).pack(anchor="w", pady=2)
            
            ctk.CTkLabel(self.options_content, text="Thay thế: Tìm →", fg_color="transparent").pack(anchor="w")
            replace_row = ctk.CTkFrame(self.options_content, fg_color="transparent")
            replace_row.pack(anchor="w", fill="x")
            self.var_replace_from = ctk.StringVar()
            self.var_replace_to = ctk.StringVar()
            ctk.CTkEntry(replace_row, textvariable=self.var_replace_from, width=70, placeholder_text="Tìm").pack(side="left")
            ctk.CTkLabel(replace_row, text="→").pack(side="left", padx=5)
            ctk.CTkEntry(replace_row, textvariable=self.var_replace_to, width=70, placeholder_text="Thay").pack(side="left")
        
        elif op == "to_csv":
            ctk.CTkLabel(self.options_content, text="Encoding:").pack(anchor="w")
            self.var_encoding = ctk.StringVar(value="utf-8-sig")
            for enc in ["utf-8-sig", "utf-8", "utf-16"]:
                ctk.CTkRadioButton(
                    self.options_content, text=enc,
                    variable=self.var_encoding, value=enc
                ).pack(anchor="w", padx=10)
            
            ctk.CTkLabel(self.options_content, text="Delimiter:").pack(anchor="w", pady=(5, 0))
            self.var_delimiter = ctk.StringVar(value=",")
            delim_row = ctk.CTkFrame(self.options_content, fg_color="transparent")
            delim_row.pack(anchor="w")
            for d, label in [(",", "Comma"), (";", "Semicolon"), ("\t", "Tab")]:
                ctk.CTkRadioButton(delim_row, text=label, variable=self.var_delimiter, value=d).pack(side="left", padx=5)
        
        elif op == "from_csv":
            ctk.CTkLabel(
                self.options_content,
                text="Mỗi file CSV → 1 sheet trong Excel",
                text_color="#9CA3AF"
            ).pack(anchor="w")
            self.var_encoding = ctk.StringVar(value="utf-8-sig")
            self.var_delimiter = ctk.StringVar(value=",")
        
        elif op == "protect":
            ctk.CTkLabel(self.options_content, text="Mật khẩu (để trống = không mật khẩu):").pack(anchor="w")
            self.var_password = ctk.StringVar()
            ctk.CTkEntry(self.options_content, textvariable=self.var_password, show="•", width=150).pack(anchor="w", pady=2)
        
        elif op == "unprotect":
            ctk.CTkLabel(
                self.options_content,
                text="Bỏ bảo vệ tất cả sheets",
                text_color="#9CA3AF"
            ).pack(anchor="w")
    
    def _setup_drag_drop(self):
        """Setup drag and drop."""
        if not HAS_TKDND:
            return
        
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self._handle_drop)
            logger.info("Drag and drop enabled for Excel Tools")
        except Exception as e:
            logger.warning(f"Could not setup drag & drop: {e}")
    
    def _handle_drop(self, event):
        """Handle dropped files."""
        try:
            file_paths = parse_dropped_paths(self, event.data)
            added = 0
            for path in file_paths:
                ext = os.path.splitext(path)[1].lower()
                if ext in ['.xlsx', '.xlsm'] and path not in self.files:
                    self.files.append(path)
                    added += 1
            
            if added > 0:
                self._refresh_file_list()
                self._log(f"📁 Thêm {added} file(s)")
        except Exception as e:
            logger.error(f"Drop error: {e}")
    
    def _browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.var_output_folder.set(folder)
            self.var_output_same.set(False)
    
    def _add_files(self):
        """Add Excel files."""
        files = filedialog.askopenfilenames(
            filetypes=[("Excel Files", "*.xlsx *.xlsm")]
        )
        for f in files:
            if f not in self.files:
                self.files.append(f)
        self._refresh_file_list()
    
    def _add_folder(self):
        """Add files from folder."""
        folder = filedialog.askdirectory()
        if not folder:
            return
        
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if ext in ['.xlsx', '.xlsm']:
                path = os.path.join(folder, f)
                if path not in self.files:
                    self.files.append(path)
        
        self._refresh_file_list()
    
    def _remove_files(self):
        """Remove selected files."""
        self._remove_selected()
    
    def _remove_selected(self):
        """Remove selected files from list."""
        selection = self.file_listbox.curselection()
        if not selection:
            if self.files:
                self.files.pop()
        else:
            for idx in sorted(selection, reverse=True):
                if 0 <= idx < len(self.files):
                    del self.files[idx]
        self._refresh_file_list()
        return "break"
    
    def _select_all_files(self):
        """Select all files."""
        if self.files:
            self.file_listbox.select_set(0, tk.END)
        return "break"
    
    def _clear_files(self):
        """Clear all files."""
        self.files.clear()
        self._refresh_file_list()
    
    def _refresh_file_list(self):
        """Refresh file list display."""
        self.file_listbox.delete(0, tk.END)
        
        for i, f in enumerate(self.files, 1):
            basename = os.path.basename(f)
            try:
                size = os.path.getsize(f) / 1024
                # Get sheet count
                info = get_sheet_info(f)
                sheet_count = len(info) if info else "?"
            except Exception:
                size = 0
                sheet_count = "?"
            
            line = f"{i}. {basename} ({size:.0f} KB, {sheet_count} sheets)"
            self.file_listbox.insert(tk.END, line)
        
        # Update count
        total_size = sum(os.path.getsize(f) for f in self.files) if self.files else 0
        if total_size > 1024 * 1024:
            size_str = f"{total_size / 1024 / 1024:.1f} MB"
        else:
            size_str = f"{total_size / 1024:.0f} KB"
        
        self.lbl_count.configure(text=f"{len(self.files)} files ({size_str})")
    
    def _log(self, msg: str):
        """Add log message."""
        self.log_textbox.insert("end", msg + "\n")
        self.log_textbox.see("end")
    
    def _start_processing(self):
        """Start processing."""
        if not self.files:
            messagebox.showwarning("Cảnh báo", "Chưa chọn file nào!")
            return
        
        if self.is_processing:
            return
        
        self.is_processing = True
        self.stop_requested = False
        self.btn_process.configure(state="disabled", text="⏳ Đang xử lý...")
        self.btn_stop.configure(state="normal")
        self.progress_bar.set(0)
        self.log_textbox.delete("1.0", "end")
        
        thread = threading.Thread(target=self._process_files, daemon=True)
        thread.start()
    
    def _stop_processing(self):
        """Stop processing."""
        self.stop_requested = True
        self._log("⏹️ Đang dừng...")
    
    def _process_files(self):
        """Process files in background thread."""
        op = self.var_operation.get()
        
        # Get output folder
        if self.var_output_same.get():
            output_dir = None
        else:
            output_dir = self.var_output_folder.get()
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
        
        try:
            if op == "split":
                self._do_split(output_dir)
            elif op == "merge":
                self._do_merge(output_dir)
            elif op == "to_csv":
                self._do_to_csv(output_dir)
            elif op == "from_csv":
                self._do_from_csv(output_dir)
            elif op == "protect":
                self._do_protect(output_dir)
            elif op == "unprotect":
                self._do_unprotect(output_dir)
            elif op == "rename":
                self._do_rename(output_dir)
        except Exception as e:
            self.after(0, lambda: self._log(f"❌ Lỗi: {e}"))
            logger.error(f"Processing error: {e}")
        finally:
            self.after(0, self._processing_complete)
    
    def _do_split(self, output_dir: Optional[str]):
        """Split each file."""
        total = len(self.files)
        success_count = 0
        
        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break
            
            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])
            
            # Determine output directory
            file_output_dir = output_dir or os.path.dirname(file_path)
            
            # Progress callback
            def on_progress(current, sheet_total, msg):
                self.after(0, lambda m=msg: self._log(f"  {m}"))
            
            # Split
            success_files, errors = split_excel(
                file_path,
                output_dir=file_output_dir,
                on_progress=on_progress
            )
            
            for sf in success_files:
                self.after(0, lambda f=sf: self._log(f"✅ {os.path.basename(f)}"))
                success_count += 1
            
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
            
            self.after(0, lambda i=idx: self.progress_bar.set((i + 1) / total))
        
        self.after(0, lambda: self._log(f"\n🎉 Hoàn thành! Tạo {success_count} file(s)"))
    
    def _do_merge(self, output_dir: Optional[str]):
        """Merge files."""
        if len(self.files) < 2:
            self.after(0, lambda: self._log("⚠️ Cần ít nhất 2 file để gộp"))
            return
        
        # Determine output path
        first_file = Path(self.files[0])
        if output_dir:
            output_path = Path(output_dir) / f"{first_file.stem}_merged.xlsx"
        else:
            output_path = first_file.parent / f"{first_file.stem}_merged.xlsx"
        
        self.after(0, lambda: self.lbl_status.configure(text="Đang gộp files..."))
        
        mode = self.var_merge_mode.get()
        skip_header = self.var_skip_header.get()
        
        def on_progress(current, total, msg):
            self.after(0, lambda: [
                self.progress_bar.set(current / total),
                self._log(f"  {msg}")
            ])
        
        result_path, errors = merge_excel(
            self.files, str(output_path), mode=mode,
            skip_header_after_first=skip_header, on_progress=on_progress
        )
        
        for err in errors:
            self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
        
        if result_path:
            self.after(0, lambda: self._log(f"\n🎉 Hoàn thành! File: {os.path.basename(result_path)}"))
        else:
            self.after(0, lambda: self._log("❌ Gộp thất bại"))
    
    def _do_to_csv(self, output_dir: Optional[str]):
        """Export Excel to CSV."""
        total = len(self.files)
        success_count = 0
        encoding = getattr(self, 'var_encoding', None)
        encoding = encoding.get() if encoding else 'utf-8-sig'
        delimiter = getattr(self, 'var_delimiter', None)
        delimiter = delimiter.get() if delimiter else ','
        
        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break
            
            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])
            
            file_output_dir = output_dir or os.path.dirname(file_path)
            
            success_files, errors = excel_to_csv(
                file_path, output_dir=file_output_dir,
                encoding=encoding, delimiter=delimiter
            )
            
            for sf in success_files:
                self.after(0, lambda f=sf: self._log(f"✅ {os.path.basename(f)}"))
                success_count += 1
            
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
        
        self.after(0, lambda: self._log(f"\n🎉 Xuất {success_count} file CSV"))
    
    def _do_from_csv(self, output_dir: Optional[str]):
        """Import CSV to Excel."""
        first_file = Path(self.files[0])
        if output_dir:
            output_path = Path(output_dir) / f"{first_file.stem}_imported.xlsx"
        else:
            output_path = first_file.parent / f"{first_file.stem}_imported.xlsx"
        
        self.after(0, lambda: self.lbl_status.configure(text="Đang nhập CSV..."))
        
        def on_progress(current, total, msg):
            self.after(0, lambda: self.progress_bar.set(current / total))
        
        result_path, errors = csv_to_excel(self.files, str(output_path), on_progress=on_progress)
        
        for err in errors:
            self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
        
        if result_path:
            self.after(0, lambda: self._log(f"\n🎉 Hoàn thành! File: {os.path.basename(result_path)}"))
    
    def _do_protect(self, output_dir: Optional[str]):
        """Protect sheets."""
        total = len(self.files)
        password = getattr(self, 'var_password', None)
        password = password.get() if password else ""
        
        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break
            
            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])
            
            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(file_path).stem}_protected.xlsx")
            else:
                out_path = str(Path(file_path).parent / f"{Path(file_path).stem}_protected.xlsx")
            
            result, errors = protect_sheets(file_path, out_path, password=password)
            
            if result:
                self.after(0, lambda f=result: self._log(f"✅ {os.path.basename(f)}"))
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
        
        self.after(0, lambda: self._log(f"\n🎉 Đã bảo vệ {total} file(s)"))
    
    def _do_unprotect(self, output_dir: Optional[str]):
        """Unprotect sheets."""
        total = len(self.files)
        
        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break
            
            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])
            
            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(file_path).stem}_unprotected.xlsx")
            else:
                out_path = str(Path(file_path).parent / f"{Path(file_path).stem}_unprotected.xlsx")
            
            result, errors = unprotect_sheets(file_path, out_path)
            
            if result:
                self.after(0, lambda f=result: self._log(f"✅ {os.path.basename(f)}"))
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
        
        self.after(0, lambda: self._log(f"\n🎉 Đã bỏ bảo vệ {total} file(s)"))
    
    def _do_rename(self, output_dir: Optional[str]):
        """Rename sheets."""
        total = len(self.files)
        prefix = getattr(self, 'var_prefix', None)
        prefix = prefix.get() if prefix else ""
        suffix = getattr(self, 'var_suffix', None)
        suffix = suffix.get() if suffix else ""
        replace_from = getattr(self, 'var_replace_from', None)
        replace_from = replace_from.get() if replace_from else ""
        replace_to = getattr(self, 'var_replace_to', None)
        replace_to = replace_to.get() if replace_to else ""
        
        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break
            
            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])
            
            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(file_path).stem}_renamed.xlsx")
            else:
                out_path = str(Path(file_path).parent / f"{Path(file_path).stem}_renamed.xlsx")
            
            result, errors = rename_sheets(
                file_path, out_path,
                prefix=prefix, suffix=suffix,
                replace_from=replace_from, replace_to=replace_to
            )
            
            if result:
                self.after(0, lambda f=result: self._log(f"✅ {os.path.basename(f)}"))
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))
        
        self.after(0, lambda: self._log(f"\n🎉 Đã đổi tên sheets trong {total} file(s)"))
    
    def _processing_complete(self):
        """Called when processing finishes."""
        self.is_processing = False
        self.btn_process.configure(state="normal", text="🚀 THỰC HIỆN")
        self.btn_stop.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text="Hoàn thành")
