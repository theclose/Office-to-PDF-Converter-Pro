"""
PDF Tools Dialog Pro - Modern CustomTkinter interface for PDF operations
Professional UI with dark theme, smooth animations, and batch processing
"""

import os
import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox
from typing import List, Optional
import logging

from office_converter.core import pdf_tools
from office_converter.utils.config import Config

logger = logging.getLogger(__name__)


class PDFToolsDialogPro(ctk.CTkToplevel):
    """Modern PDF Tools dialog with CustomTkinter."""
    
    # Operation categories
    OPERATIONS = {
        "edit": [
            ("merge", "📎 Gộp PDF", "Gộp nhiều file thành 1"),
            ("split", "✂️ Tách PDF", "Tách thành nhiều file"),
            ("extract", "📑 Trích xuất", "Lấy các trang cụ thể"),
            ("delete", "🗑️ Xóa trang", "Xóa các trang chỉ định"),
            ("rotate", "🔄 Xoay", "Xoay trang 90°/180°/270°"),
            ("reverse", "🔃 Đảo ngược", "Đảo thứ tự trang"),
        ],
        "convert": [
            ("pdf_to_img", "🖼️ PDF → Ảnh", "Xuất mỗi trang thành ảnh"),
            ("img_to_pdf", "📄 Ảnh → PDF", "Gộp ảnh thành PDF"),
            ("ocr", "🔍 OCR", "Scan PDF thành text"),
        ],
        "optimize": [
            ("compress", "📦 Nén", "Giảm dung lượng file"),
            ("protect", "🔒 Mật khẩu", "Bảo vệ bằng password"),
            ("watermark", "💧 Watermark", "Thêm watermark text"),
        ],
    }
    
    # All operation keys for validation
    ALL_OPERATIONS = ["merge", "split", "extract", "delete", "rotate", "reverse",
                      "pdf_to_img", "img_to_pdf", "ocr", "compress", "protect", "watermark"]
    
    def __init__(self, parent, lang: str = "vi"):
        super().__init__(parent)
        
        self.parent = parent
        self.lang = lang
        self.files: List[str] = []
        self.is_processing = False
        self.stop_requested = False
        self.compression_results = {}
        
        # Load config for remembering last operation
        self.config = Config()
        
        # Window setup
        self.title("🛠️ PDF Tools Pro")
        self.geometry("1000x700")
        self.minsize(900, 600)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1000) // 2
        y = (self.winfo_screenheight() - 700) // 2
        self.geometry(f"+{x}+{y}")
        
        # Get last used operation from config (default to compress)
        last_op = self.config.get("pdf_tools_last_operation", "compress")
        if last_op not in self.ALL_OPERATIONS:
            last_op = "compress"
        
        # Variables
        self.var_operation = ctk.StringVar(value=last_op)
        self.var_quality = ctk.StringVar(value="medium")
        self.var_rotation = ctk.IntVar(value=90)
        self.var_page_range = ctk.StringVar(value="1-3")
        self.var_watermark_text = ctk.StringVar(value="CONFIDENTIAL")
        self.var_password = ctk.StringVar()
        self.var_dpi = ctk.IntVar(value=150)
        self.var_image_format = ctk.StringVar(value="png")
        self.var_output_same = ctk.BooleanVar(value=True)
        self.var_output_folder = ctk.StringVar()
        
        self._create_ui()
        
        # Set the correct tab based on last operation
        self._switch_to_operation_tab(last_op)
        
        # Modal behavior
        self.transient(parent)
        self.grab_set()
        
        # Save operation when closing
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _on_close(self):
        """Save last operation and close."""
        self.config.set("pdf_tools_last_operation", self.var_operation.get())
        self.config.save()
        self.destroy()
    
    def _switch_to_operation_tab(self, op: str):
        """Switch to the tab containing the given operation."""
        try:
            if op in ["merge", "split", "extract", "delete", "rotate", "reverse"]:
                self.tab_view.set("✏️ Chỉnh sửa")
            elif op in ["pdf_to_img", "img_to_pdf", "ocr"]:
                self.tab_view.set("🔄 Chuyển đổi")
            elif op in ["compress", "protect", "watermark"]:
                self.tab_view.set("⚡ Tối ưu")
        except Exception:
            pass  # Tab may not exist yet
    
    def _create_ui(self):
        """Build the modern UI."""
        # Main container with 2 columns
        self.grid_columnconfigure(0, weight=0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # === LEFT PANEL: Operations & Options ===
        left_panel = ctk.CTkFrame(self, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.grid_rowconfigure(2, weight=1)
        
        # Header
        header = ctk.CTkFrame(left_panel, fg_color="#1F2937", corner_radius=0)
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, 
            text="🛠️ PDF Tools Pro",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(pady=15)
        
        # --- Operations Tabs ---
        self.tab_view = ctk.CTkTabview(left_panel, height=250)
        self.tab_view.pack(fill="x", padx=10, pady=(0, 10))
        
        # Create tabs
        tab_edit = self.tab_view.add("✏️ Chỉnh sửa")
        tab_convert = self.tab_view.add("🔄 Chuyển đổi")
        tab_optimize = self.tab_view.add("⚡ Tối ưu")
        
        # Populate tabs
        self._create_operation_buttons(tab_edit, self.OPERATIONS["edit"])
        self._create_operation_buttons(tab_convert, self.OPERATIONS["convert"])
        self._create_operation_buttons(tab_optimize, self.OPERATIONS["optimize"])
        
        # --- Options Panel ---
        self.options_frame = ctk.CTkFrame(left_panel)
        self.options_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(
            self.options_frame, 
            text="⚙️ Tùy chọn",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))
        
        self.options_content = ctk.CTkFrame(self.options_frame, fg_color="transparent")
        self.options_content.pack(fill="x", padx=10, pady=(0, 10))
        
        self._update_options_panel()
        
        # --- Output Settings ---
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
            width=80
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
        
        # --- Action Buttons ---
        action_frame = ctk.CTkFrame(left_panel)
        action_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_process = ctk.CTkButton(
            action_frame,
            text="🚀 THỰC HIỆN",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color="#22C55E",
            hover_color="#16A34A",
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
            command=self.destroy
        ).pack(side="right")
        
        # === RIGHT PANEL: Files & Progress ===
        right_panel = ctk.CTkFrame(self, fg_color="transparent")
        right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)
        
        # File list header
        file_header = ctk.CTkFrame(right_panel)
        file_header.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ctk.CTkLabel(
            file_header, 
            text="📁 Danh sách Files",
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
        
        self.file_listbox = ctk.CTkTextbox(
            file_list_frame, 
            height=200,
            font=ctk.CTkFont(family="Consolas", size=12)
        )
        self.file_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.file_listbox.configure(state="disabled")
        
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
        
        self.progress_bar = ctk.CTkProgressBar(progress_frame, height=20)
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.set(0)
        
        self.lbl_progress = ctk.CTkLabel(
            progress_frame, 
            text="",
            text_color="#9CA3AF"
        )
        self.lbl_progress.pack(pady=(0, 5))
        
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
            height=150,
            font=ctk.CTkFont(family="Consolas", size=11)
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    
    def _create_operation_buttons(self, parent, operations):
        """Create operation buttons in a grid."""
        for i, (key, label, desc) in enumerate(operations):
            row = i // 2
            col = i % 2
            
            btn = ctk.CTkButton(
                parent,
                text=label,
                width=130,
                height=40,
                fg_color="#374151" if self.var_operation.get() != key else "#3B82F6",
                hover_color="#4B5563",
                command=lambda k=key: self._select_operation(k)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="ew")
            
            # Store reference
            if not hasattr(self, '_op_buttons'):
                self._op_buttons = {}
            self._op_buttons[key] = btn
    
    def _select_operation(self, op: str):
        """Select an operation and update UI."""
        self.var_operation.set(op)
        
        # Update button colors
        for key, btn in self._op_buttons.items():
            if key == op:
                btn.configure(fg_color="#3B82F6")
            else:
                btn.configure(fg_color="#374151")
        
        self._update_options_panel()
    
    def _update_options_panel(self):
        """Update options panel based on selected operation."""
        # Clear current options
        for widget in self.options_content.winfo_children():
            widget.destroy()
        
        op = self.var_operation.get()
        
        if op == "compress":
            ctk.CTkLabel(self.options_content, text="Chất lượng:").pack(anchor="w")
            for val, text in [("low", "🔹 Thấp (nhỏ nhất)"), 
                              ("medium", "🔸 Trung bình"), 
                              ("high", "🔶 Cao (chất lượng)")]:
                ctk.CTkRadioButton(
                    self.options_content, text=text,
                    variable=self.var_quality, value=val
                ).pack(anchor="w", padx=10)
                
        elif op == "rotate":
            ctk.CTkLabel(self.options_content, text="Góc xoay:").pack(anchor="w")
            for val in [90, 180, 270]:
                ctk.CTkRadioButton(
                    self.options_content, text=f"{val}°",
                    variable=self.var_rotation, value=val
                ).pack(anchor="w", padx=10)
                
        elif op in ["extract", "delete"]:
            ctk.CTkLabel(self.options_content, text="Số trang (vd: 1-5, 8, 10-12):").pack(anchor="w")
            ctk.CTkEntry(
                self.options_content, 
                textvariable=self.var_page_range,
                width=200
            ).pack(anchor="w", pady=5)
            
        elif op == "watermark":
            ctk.CTkLabel(self.options_content, text="Text watermark:").pack(anchor="w")
            ctk.CTkEntry(
                self.options_content, 
                textvariable=self.var_watermark_text,
                width=200
            ).pack(anchor="w", pady=5)
            
        elif op == "protect":
            ctk.CTkLabel(self.options_content, text="Mật khẩu:").pack(anchor="w")
            ctk.CTkEntry(
                self.options_content, 
                textvariable=self.var_password,
                show="•",
                width=200
            ).pack(anchor="w", pady=5)
            
        elif op == "pdf_to_img":
            ctk.CTkLabel(self.options_content, text="DPI:").pack(anchor="w")
            ctk.CTkSlider(
                self.options_content, 
                from_=72, to=300,
                variable=self.var_dpi,
                width=180
            ).pack(anchor="w", pady=5)
            
            ctk.CTkLabel(self.options_content, text="Định dạng:").pack(anchor="w")
            for fmt in ["png", "jpg"]:
                ctk.CTkRadioButton(
                    self.options_content, text=fmt.upper(),
                    variable=self.var_image_format, value=fmt
                ).pack(anchor="w", padx=10)
        else:
            ctk.CTkLabel(
                self.options_content, 
                text="Không có tùy chọn",
                text_color="#6B7280"
            ).pack(anchor="w")
    
    def _browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.var_output_folder.set(folder)
            self.var_output_same.set(False)
    
    def _add_files(self):
        """Add PDF files."""
        op = self.var_operation.get()
        if op == "img_to_pdf":
            filetypes = [("Images", "*.png *.jpg *.jpeg *.bmp *.gif")]
        else:
            filetypes = [("PDF Files", "*.pdf")]
        
        files = filedialog.askopenfilenames(filetypes=filetypes)
        for f in files:
            if f not in self.files:
                self.files.append(f)
        self._refresh_file_list()
    
    def _add_folder(self):
        """Add files from folder."""
        folder = filedialog.askdirectory()
        if not folder:
            return
        
        op = self.var_operation.get()
        if op == "img_to_pdf":
            exts = [".png", ".jpg", ".jpeg", ".bmp", ".gif"]
        else:
            exts = [".pdf"]
        
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if ext in exts:
                path = os.path.join(folder, f)
                if path not in self.files:
                    self.files.append(path)
        
        self._refresh_file_list()
    
    def _remove_files(self):
        """Remove selected file (last one for now)."""
        if self.files:
            self.files.pop()
            self._refresh_file_list()
    
    def _clear_files(self):
        """Clear all files."""
        self.files.clear()
        self.compression_results.clear()
        self._refresh_file_list()
    
    def _refresh_file_list(self):
        """Refresh the file list display."""
        self.file_listbox.configure(state="normal")
        self.file_listbox.delete("1.0", "end")
        
        for i, f in enumerate(self.files, 1):
            basename = os.path.basename(f)
            size = os.path.getsize(f) / 1024  # KB
            
            # Show compression results if available
            if f in self.compression_results:
                orig, new = self.compression_results[f]
                ratio = (1 - new/orig) * 100 if orig > 0 else 0
                line = f"{i}. {basename} ({size:.0f}KB → {new/1024:.0f}KB, -{ratio:.0f}%)\n"
            else:
                line = f"{i}. {basename} ({size:.0f} KB)\n"
            
            self.file_listbox.insert("end", line)
        
        self.file_listbox.configure(state="disabled")
        
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
        """Start batch processing."""
        if not self.files:
            messagebox.showwarning("Cảnh báo", "Chưa chọn file nào!")
            return
        
        if self.is_processing:
            return
        
        op = self.var_operation.get()
        
        # Special: merge needs output path
        if op == "merge":
            self._do_merge()
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
        total = len(self.files)
        success = 0
        
        # Get output folder
        if self.var_output_same.get():
            output_folder = None  # Use same folder as input
        else:
            output_folder = self.var_output_folder.get()
            if output_folder:
                os.makedirs(output_folder, exist_ok=True)
        
        # Get suffix
        suffixes = {
            "compress": "_compressed",
            "rotate": "_rotated",
            "extract": "_extracted",
            "delete": "_deleted",
            "reverse": "_reversed",
            "watermark": "_watermarked",
            "protect": "_protected",
            "pdf_to_img": "",
            "split": "_split",
            "img_to_pdf": ".pdf",
            "ocr": "_ocr",
        }
        suffix = suffixes.get(op, "_output")
        
        for i, input_path in enumerate(self.files):
            if self.stop_requested:
                break
            
            basename = os.path.basename(input_path)
            name, ext = os.path.splitext(basename)
            
            # Determine output path
            if output_folder:
                if op == "pdf_to_img":
                    output_path = output_folder
                else:
                    output_path = os.path.join(output_folder, name + suffix + ".pdf")
            else:
                parent = os.path.dirname(input_path)
                if op == "pdf_to_img":
                    output_path = parent
                else:
                    output_path = os.path.join(parent, name + suffix + ".pdf")
            
            # Update status
            self.after(0, lambda b=basename, idx=i+1: [
                self.lbl_status.configure(text=f"({idx}/{total}) {b}"),
                self.progress_bar.set(idx / total)
            ])
            
            try:
                result = self._execute_operation(op, input_path, output_path)
                if result:
                    success += 1
                    self.after(0, lambda b=basename: self._log(f"✅ {b}"))
                else:
                    self.after(0, lambda b=basename: self._log(f"❌ {b}"))
            except Exception as e:
                self.after(0, lambda b=basename, err=str(e): self._log(f"❌ {b}: {err}"))
        
        self.after(0, lambda: self._on_done(success, total))
    
    def _execute_operation(self, op: str, input_path: str, output_path: str) -> bool:
        """Execute single operation."""
        try:
            if op == "compress":
                orig_size = os.path.getsize(input_path)
                result, _ = pdf_tools.compress_pdf(input_path, output_path, self.var_quality.get())
                if result and os.path.exists(output_path):
                    new_size = os.path.getsize(output_path)
                    self.compression_results[input_path] = (orig_size, new_size)
                    self.after(0, self._refresh_file_list)
                return result
            elif op == "protect":
                pwd = self.var_password.get()
                return pdf_tools.protect_pdf(input_path, output_path, pwd) if pwd else False
            elif op == "rotate":
                return pdf_tools.rotate_pages(input_path, output_path, self.var_rotation.get())
            elif op == "extract":
                ok, _ = pdf_tools.extract_pages(input_path, output_path, self.var_page_range.get())
                return ok
            elif op == "delete":
                ok, _ = pdf_tools.delete_pages(input_path, output_path, self.var_page_range.get())
                return ok
            elif op == "reverse":
                return pdf_tools.reverse_pages(input_path, output_path)
            elif op == "watermark":
                return pdf_tools.add_watermark(input_path, output_path, self.var_watermark_text.get())
            elif op == "pdf_to_img":
                imgs = pdf_tools.pdf_to_images(input_path, output_path, self.var_dpi.get(), self.var_image_format.get())
                return len(imgs) > 0
            elif op == "split":
                return pdf_tools.split_pdf(input_path, output_path)
            elif op == "img_to_pdf":
                return pdf_tools.images_to_pdf([input_path], output_path)
            elif op == "ocr":
                from office_converter.utils.ocr import ocr_pdf_to_searchable, is_ocr_available
                if not is_ocr_available():
                    return False
                return ocr_pdf_to_searchable(input_path, output_path, lang=None)
            return False
        except Exception as e:
            logger.error(f"Operation {op} failed: {e}")
            return False
    
    def _do_merge(self):
        """Merge PDFs."""
        if len(self.files) < 2:
            messagebox.showwarning("Cảnh báo", "Cần ít nhất 2 file để gộp!")
            return
        
        if self.var_output_same.get():
            output = os.path.join(os.path.dirname(self.files[0]), "merged.pdf")
            counter = 1
            while os.path.exists(output):
                output = os.path.join(os.path.dirname(self.files[0]), f"merged_{counter}.pdf")
                counter += 1
        else:
            output = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile="merged.pdf"
            )
            if not output:
                return
        
        self._log(f"📎 Gộp {len(self.files)} files...")
        result = pdf_tools.merge_pdfs(self.files, output)
        
        if result:
            self._log(f"✅ Đã gộp thành: {os.path.basename(output)}")
            # Ask to open folder
            output_folder = os.path.dirname(output)
            open_folder = messagebox.askyesno(
                "✅ Thành công",
                f"Đã gộp {len(self.files)} files!\n\n"
                f"File: {os.path.basename(output)}\n\n"
                f"Mở thư mục chứa file?",
                parent=self
            )
            if open_folder:
                try:
                    os.startfile(output_folder)
                except Exception as e:
                    self._log(f"❌ Không thể mở folder: {e}")
        else:
            self._log("❌ Gộp thất bại!")
            messagebox.showerror("Lỗi", "Không thể gộp PDF!")
    
    def _on_done(self, success: int, total: int):
        """Processing complete."""
        self.is_processing = False
        self.btn_process.configure(state="normal", text="🚀 THỰC HIỆN")
        self.btn_stop.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text=f"✅ Xong: {success}/{total}")
        self._log(f"\n🎉 Hoàn thành: {success}/{total} files")
        
        # Show completion dialog with Open Folder option
        if success > 0:
            output_folder = self.var_output.get()
            if output_folder and os.path.exists(output_folder):
                result = messagebox.askyesno(
                    "✅ Hoàn thành",
                    f"Đã xử lý thành công {success}/{total} files.\n\n"
                    f"Mở thư mục chứa file đã xử lý?",
                    parent=self
                )
                if result:
                    try:
                        os.startfile(output_folder)
                    except Exception as e:
                        self._log(f"❌ Không thể mở folder: {e}")
            else:
                messagebox.showinfo(
                    "✅ Hoàn thành",
                    f"Đã xử lý thành công {success}/{total} files.",
                    parent=self
                )


def show_pdf_tools_pro(parent, lang: str = "vi"):
    """Show the PDF Tools Pro dialog."""
    PDFToolsDialogPro(parent, lang)
