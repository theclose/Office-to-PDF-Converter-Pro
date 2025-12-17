"""
PDF Tools Dialog - Unified interface for all PDF operations
Supports batch processing with progress tracking
Compact layout to show all controls without scrolling
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List

from office_converter.core import pdf_tools
from office_converter.utils.config import Config


class PDFToolsDialog:
    """Unified dialog for all PDF operations with batch support."""
    
    # Operation definitions with icons
    OPERATIONS = [
        ("merge", "📎 Gộp PDF"),
        ("split", "✂️ Tách PDF"),
        ("compress", "📦 Nén"),
        ("protect", "🔒 Mật khẩu"),
        ("rotate", "🔄 Xoay"),
        ("extract", "📑 Trích"),
        ("delete", "🗑️ Xóa trang"),
        ("reverse", "🔃 Đảo ngược"),
        ("watermark", "💧 Watermark"),
        ("pdf_to_img", "🖼️ PDF→Ảnh"),
        ("img_to_pdf", "📄 Ảnh→PDF"),
        ("ocr", "🔍 OCR"),
    ]
    
    # All valid operations for validation
    ALL_OPS = ["merge", "split", "compress", "protect", "rotate", "extract", 
               "delete", "reverse", "watermark", "pdf_to_img", "img_to_pdf", "ocr"]
    
    def __init__(self, parent, lang: str = "vi"):
        self.parent = parent
        self.lang = lang
        self.files: List[str] = []
        self.is_processing = False
        self.stop_requested = False
        
        # Load config for remembering last operation
        self.config = Config()
        
        self._create_dialog()
    
    def _create_dialog(self):
        """Create the dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("🛠️ PDF Tools")
        self.dialog.geometry("850x600")
        self.dialog.minsize(800, 550)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Get last used operation (default to compress)
        last_op = self.config.get("pdf_tools_last_operation", "compress")
        if last_op not in self.ALL_OPS:
            last_op = "compress"
        
        # Variables
        self.var_operation = tk.StringVar(value=last_op)
        self.var_quality = tk.StringVar(value="medium")
        self.var_rotation = tk.IntVar(value=90)
        self.var_page_range = tk.StringVar(value="1-3")
        self.var_watermark_text = tk.StringVar(value="CONFIDENTIAL")
        self.var_password = tk.StringVar()
        self.var_dpi = tk.IntVar(value=150)
        self.var_image_format = tk.StringVar(value="png")
        self.var_output_same = tk.BooleanVar(value=True)
        self.var_output_folder = tk.StringVar()
        
        # Store compression results for display
        self.compression_results = {}  # {filepath: (original_size, compressed_size)}
        
        # Save on close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._build_ui()
    
    def _on_close(self):
        """Save last operation and close."""
        self.config.set("pdf_tools_last_operation", self.var_operation.get())
        self.config.save()
        self.dialog.destroy()
    
    def _build_ui(self):
        """Build the dialog UI with compact layout."""
        # Main container with two columns
        main_frame = ttk.Frame(self.dialog, padding=5)
        main_frame.pack(fill="both", expand=True)
        
        # === LEFT COLUMN: Operations + Options ===
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side="left", fill="both", expand=False, padx=(0, 5))
        
        # Operations (2 columns of buttons)
        frame_op = ttk.LabelFrame(left_frame, text="📋 Thao tác", padding=5)
        frame_op.pack(fill="x", pady=(0, 5))
        
        for i, (key, label) in enumerate(self.OPERATIONS):
            row = i // 2
            col = i % 2
            btn = ttk.Radiobutton(frame_op, text=label, variable=self.var_operation,
                                  value=key, command=self._on_operation_change, width=14)
            btn.grid(row=row, column=col, padx=2, pady=1, sticky="w")
        
        # Options panel
        self.frame_options = ttk.LabelFrame(left_frame, text="⚙️ Tùy chọn", padding=5)
        self.frame_options.pack(fill="x", pady=(0, 5))
        self._build_options_panel()
        
        # Output settings (compact)
        frame_output = ttk.LabelFrame(left_frame, text="📂 Output", padding=5)
        frame_output.pack(fill="x", pady=(0, 5))
        
        ttk.Radiobutton(frame_output, text="Cùng folder với file gốc",
                        variable=self.var_output_same, value=True).pack(anchor="w")
        row_out = ttk.Frame(frame_output)
        row_out.pack(fill="x")
        ttk.Radiobutton(row_out, text="Khác:",
                        variable=self.var_output_same, value=False).pack(side="left")
        ttk.Entry(row_out, textvariable=self.var_output_folder, width=20).pack(side="left", padx=2)
        ttk.Button(row_out, text="...", width=3, command=self._browse_output).pack(side="left")
        
        # Action buttons (prominent)
        frame_actions = ttk.LabelFrame(left_frame, text="▶️ Thực hiện", padding=5)
        frame_actions.pack(fill="x")
        
        self.btn_process = tk.Button(frame_actions, text="🚀 THỰC HIỆN", 
                                      command=self._start_processing,
                                      bg="#4CAF50", fg="white", font=("", 11, "bold"),
                                      width=18, height=1, cursor="hand2")
        self.btn_process.pack(side="left", padx=2, pady=2)
        
        self.btn_stop = ttk.Button(frame_actions, text="⏹ Dừng",
                                    command=self._stop_processing, state="disabled", width=8)
        self.btn_stop.pack(side="left", padx=2)
        
        ttk.Button(frame_actions, text="Đóng", command=self.dialog.destroy, width=8).pack(side="right", padx=2)
        
        # === RIGHT COLUMN: File List + Progress ===
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)
        
        # File list
        frame_files = ttk.LabelFrame(right_frame, text="📁 Danh sách Files", padding=5)
        frame_files.pack(fill="both", expand=True, pady=(0, 5))
        
        # File buttons (compact row)
        btn_row = ttk.Frame(frame_files)
        btn_row.pack(fill="x", pady=(0, 3))
        
        ttk.Button(btn_row, text="➕ Files", command=self._add_files, width=8).pack(side="left", padx=1)
        ttk.Button(btn_row, text="📁 Folder", command=self._add_folder, width=8).pack(side="left", padx=1)
        ttk.Button(btn_row, text="🗑️ Xóa", command=self._remove_files, width=6).pack(side="left", padx=1)
        ttk.Button(btn_row, text="🗑️ Hết", command=self._clear_files, width=5).pack(side="left", padx=1)
        ttk.Button(btn_row, text="⬆️", command=self._move_up, width=2).pack(side="left", padx=1)
        ttk.Button(btn_row, text="⬇️", command=self._move_down, width=2).pack(side="left", padx=1)
        self.lbl_count = ttk.Label(btn_row, text="0 files", font=("", 9, "bold"))
        self.lbl_count.pack(side="right")
        
        # Listbox
        list_container = ttk.Frame(frame_files)
        list_container.pack(fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side="right", fill="y")
        
        self.listbox = tk.Listbox(list_container, selectmode="extended", 
                                   yscrollcommand=scrollbar.set, font=("Consolas", 9))
        self.listbox.pack(fill="both", expand=True)
        scrollbar.config(command=self.listbox.yview)
        
        # Progress section (compact)
        frame_progress = ttk.LabelFrame(right_frame, text="📊 Tiến trình", padding=5)
        frame_progress.pack(fill="x")
        
        self.progress = ttk.Progressbar(frame_progress, mode="determinate")
        self.progress.pack(fill="x")
        
        self.lbl_status = ttk.Label(frame_progress, text="Sẵn sàng", font=("", 9))
        self.lbl_status.pack(anchor="w")
        
        # Log (compact)
        log_container = ttk.Frame(frame_progress)
        log_container.pack(fill="x")
        
        log_scroll = ttk.Scrollbar(log_container)
        log_scroll.pack(side="right", fill="y")
        
        self.log_text = tk.Text(log_container, height=4, state="disabled", 
                                 font=("Consolas", 8), yscrollcommand=log_scroll.set)
        self.log_text.pack(fill="x")
        log_scroll.config(command=self.log_text.yview)
    
    def _build_options_panel(self):
        """Build options panel based on selected operation."""
        for widget in self.frame_options.winfo_children():
            widget.destroy()
        
        op = self.var_operation.get()
        
        if op == "merge":
            ttk.Label(self.frame_options, text="Gộp tất cả files thành 1 PDF", font=("", 8)).pack(anchor="w")
        
        elif op == "split":
            ttk.Label(self.frame_options, text="Tách mỗi trang thành 1 file", font=("", 8)).pack(anchor="w")
        
        elif op == "compress":
            row = ttk.Frame(self.frame_options)
            row.pack(fill="x")
            ttk.Radiobutton(row, text="Thấp", variable=self.var_quality, value="low").pack(side="left")
            ttk.Radiobutton(row, text="TB ✓", variable=self.var_quality, value="medium").pack(side="left", padx=5)
            ttk.Radiobutton(row, text="Cao", variable=self.var_quality, value="high").pack(side="left")
            ttk.Label(self.frame_options, text="💡 Sau khi nén sẽ hiển thị dung lượng", 
                      font=("", 7), foreground="gray").pack(anchor="w")
        
        elif op == "protect":
            row = ttk.Frame(self.frame_options)
            row.pack(fill="x")
            ttk.Label(row, text="🔒 Mật khẩu:").pack(side="left")
            self.entry_password = ttk.Entry(row, textvariable=self.var_password, width=20, show="*")
            self.entry_password.pack(side="left", padx=3)
            ttk.Label(row, text="(để mở file)", font=("", 8), foreground="gray").pack(side="left")
        
        elif op == "rotate":
            row = ttk.Frame(self.frame_options)
            row.pack(fill="x")
            ttk.Radiobutton(row, text="90° →", variable=self.var_rotation, value=90).pack(side="left")
            ttk.Radiobutton(row, text="180°", variable=self.var_rotation, value=180).pack(side="left", padx=5)
            ttk.Radiobutton(row, text="270° ←", variable=self.var_rotation, value=270).pack(side="left")
        
        elif op in ["extract", "delete"]:
            row = ttk.Frame(self.frame_options)
            row.pack(fill="x")
            ttk.Label(row, text="Trang:").pack(side="left")
            ttk.Entry(row, textvariable=self.var_page_range, width=15).pack(side="left", padx=3)
            ttk.Label(row, text="(VD: 1-5, 7)", font=("", 8), foreground="gray").pack(side="left")
        
        elif op == "watermark":
            row = ttk.Frame(self.frame_options)
            row.pack(fill="x")
            ttk.Label(row, text="Text:").pack(side="left")
            ttk.Entry(row, textvariable=self.var_watermark_text, width=20).pack(side="left", padx=3)
        
        elif op == "pdf_to_img":
            row = ttk.Frame(self.frame_options)
            row.pack(fill="x")
            ttk.Label(row, text="DPI:").pack(side="left")
            ttk.Spinbox(row, from_=72, to=300, textvariable=self.var_dpi, width=5).pack(side="left", padx=3)
            ttk.Radiobutton(row, text="PNG", variable=self.var_image_format, value="png").pack(side="left")
            ttk.Radiobutton(row, text="JPG", variable=self.var_image_format, value="jpg").pack(side="left")
        
        elif op == "img_to_pdf":
            ttk.Label(self.frame_options, text="Gộp ảnh thành PDF", font=("", 8)).pack(anchor="w")
        
        elif op == "reverse":
            ttk.Label(self.frame_options, text="Đảo ngược thứ tự trang", font=("", 8)).pack(anchor="w")
    
    def _on_operation_change(self):
        """Handle operation change."""
        self._build_options_panel()
    
    def _add_files(self):
        """Add files to the list."""
        op = self.var_operation.get()
        if op == "img_to_pdf":
            filetypes = [("Images", "*.png *.jpg *.jpeg *.bmp *.gif")]
        else:
            filetypes = [("PDF Files", "*.pdf")]
        
        files = filedialog.askopenfilenames(filetypes=filetypes)
        for f in files:
            if f not in self.files:
                self.files.append(f)
        self._refresh_listbox()
    
    def _add_folder(self):
        """Add all files from a folder."""
        folder = filedialog.askdirectory()
        if folder:
            op = self.var_operation.get()
            exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif") if op == "img_to_pdf" else (".pdf",)
            
            for f in sorted(os.listdir(folder)):
                if f.lower().endswith(exts):
                    full_path = os.path.join(folder, f)
                    if full_path not in self.files:
                        self.files.append(full_path)
        self._refresh_listbox()
    
    def _remove_files(self):
        """Remove selected files."""
        selected = list(self.listbox.curselection())
        for idx in reversed(selected):
            del self.files[idx]
        self._refresh_listbox()
    
    def _clear_files(self):
        """Clear all files."""
        self.files.clear()
        self._refresh_listbox()
    
    def _move_up(self):
        """Move selected file up."""
        selected = self.listbox.curselection()
        if selected and selected[0] > 0:
            idx = selected[0]
            self.files[idx], self.files[idx-1] = self.files[idx-1], self.files[idx]
            self._refresh_listbox()
            self.listbox.selection_set(idx - 1)
    
    def _move_down(self):
        """Move selected file down."""
        selected = self.listbox.curselection()
        if selected and selected[0] < len(self.files) - 1:
            idx = selected[0]
            self.files[idx], self.files[idx+1] = self.files[idx+1], self.files[idx]
            self._refresh_listbox()
            self.listbox.selection_set(idx + 1)
    
    def _refresh_listbox(self):
        """Refresh listbox with numbered items and file sizes."""
        self.listbox.delete(0, "end")
        total_size = 0
        
        for i, f in enumerate(self.files, 1):
            filename = os.path.basename(f)
            
            # Get file size
            try:
                size_bytes = os.path.getsize(f)
                total_size += size_bytes
                
                # Format size
                if size_bytes >= 1024 * 1024:
                    size_str = f"{size_bytes / 1024 / 1024:.1f} MB"
                else:
                    size_str = f"{size_bytes / 1024:.0f} KB"
                
                # Check if we have compression result for this file
                if f in self.compression_results:
                    orig, comp = self.compression_results[f]
                    reduction = (1 - comp / orig) * 100 if orig > 0 else 0
                    display = f"{i:02d}. {filename} [{size_str}] → [{comp/1024:.0f} KB] (-{reduction:.0f}%)"
                else:
                    display = f"{i:02d}. {filename} [{size_str}]"
            except Exception:
                display = f"{i:02d}. {filename}"
            
            self.listbox.insert("end", display)
        
        # Update count with total size
        if total_size >= 1024 * 1024:
            size_info = f"{total_size / 1024 / 1024:.1f} MB"
        else:
            size_info = f"{total_size / 1024:.0f} KB"
        
        self.lbl_count.config(text=f"{len(self.files)} files ({size_info})")
    
    def _browse_output(self):
        """Browse for output folder."""
        folder = filedialog.askdirectory()
        if folder:
            self.var_output_folder.set(folder)
            self.var_output_same.set(False)
    
    def _log(self, message: str):
        """Add message to log."""
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
    
    def _start_processing(self):
        """Start batch processing."""
        if not self.files:
            messagebox.showwarning("Warning", "Chưa chọn file nào!")
            return
        
        op = self.var_operation.get()
        
        # Special case: Merge needs output file selection
        if op == "merge":
            # If "same folder" is selected, auto-generate output path
            if self.var_output_same.get():
                first_file_dir = os.path.dirname(self.files[0])
                output = os.path.join(first_file_dir, "merged.pdf")
                # Avoid overwrite: add number if exists
                counter = 1
                while os.path.exists(output):
                    output = os.path.join(first_file_dir, f"merged_{counter}.pdf")
                    counter += 1
            else:
                output = filedialog.asksaveasfilename(
                    defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile="merged.pdf"
                )
                if not output:
                    return
            self._do_merge(output)
            return
        
        self.is_processing = True
        self.stop_requested = False
        self.btn_process.config(state="disabled", bg="gray")
        self.btn_stop.config(state="normal")
        self.progress["value"] = 0
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        
        thread = threading.Thread(target=self._process_files, daemon=True)
        thread.start()
    
    def _do_merge(self, output_path: str):
        """Merge all PDFs into one."""
        self._log("🔄 Đang gộp PDF...")
        try:
            success = pdf_tools.merge_pdfs(self.files, output_path)
            if success:
                self._log(f"✅ Đã gộp {len(self.files)} files")
                output_folder = os.path.dirname(output_path)
                self._show_success_dialog(f"Đã gộp {len(self.files)} files!", output_folder)
            else:
                self._log("❌ Gộp PDF thất bại")
                messagebox.showerror("Lỗi", "Không thể gộp PDF!")
        except Exception as e:
            self._log(f"❌ Lỗi: {str(e)}")
            messagebox.showerror("Lỗi", str(e))
    
    def _stop_processing(self):
        """Stop processing."""
        self.stop_requested = True
        self.btn_stop.config(state="disabled")
    
    def _process_files(self):
        """Process all files in background thread."""
        op = self.var_operation.get()
        total = len(self.files)
        success = 0
        
        for i, input_path in enumerate(self.files):
            if self.stop_requested:
                self.dialog.after(0, lambda: self._log("⏹️ Dừng!"))
                break
            
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_folder = os.path.dirname(input_path) if self.var_output_same.get() else (self.var_output_folder.get() or os.path.dirname(input_path))
            
            suffix = {"compress": "_compressed", "protect": "_protected", "rotate": "_rotated", 
                     "extract": "_extracted", "delete": "_deleted", "reverse": "_reversed", 
                     "watermark": "_watermarked", "pdf_to_img": "_images", "split": "_pages"}.get(op, "_processed")
            
            if op in ["pdf_to_img", "split"]:
                output_path = os.path.join(output_folder, base_name + suffix)
            else:
                output_path = os.path.join(output_folder, base_name + suffix + ".pdf")
            
            self.dialog.after(0, lambda f=base_name, idx=i+1: self.lbl_status.config(text=f"({idx}/{total}) {f}..."))
            
            try:
                result = self._execute_operation(op, input_path, output_path)
                if result:
                    success += 1
                    self.dialog.after(0, lambda f=base_name: self._log(f"✅ {f}"))
                else:
                    self.dialog.after(0, lambda f=base_name: self._log(f"❌ {f}"))
            except Exception as e:
                self.dialog.after(0, lambda f=base_name, err=str(e): self._log(f"❌ {f}: {err}"))
            
            self.dialog.after(0, lambda v=(i+1)/total*100: self.progress.configure(value=v))
        
        self.dialog.after(0, lambda: self._on_done(success, total))
    
    def _execute_operation(self, op: str, input_path: str, output_path: str) -> bool:
        """Execute a single operation."""
        if op == "compress":
            # Get original size for comparison
            orig_size = os.path.getsize(input_path)
            result, _ = pdf_tools.compress_pdf(input_path, output_path, self.var_quality.get())
            if result and os.path.exists(output_path):
                # Store compression result for display
                new_size = os.path.getsize(output_path)
                self.compression_results[input_path] = (orig_size, new_size)
                self.dialog.after(0, self._refresh_listbox)
            return result
        elif op == "protect":
            password = self.var_password.get()
            if not password:
                return False
            return pdf_tools.protect_pdf(input_path, output_path, password)
        elif op == "rotate":
            return pdf_tools.rotate_pages(input_path, output_path, self.var_rotation.get())
        elif op == "extract":
            result, _ = pdf_tools.extract_pages(input_path, output_path, self.var_page_range.get())
            return result
        elif op == "delete":
            result, _ = pdf_tools.delete_pages(input_path, output_path, self.var_page_range.get())
            return result
        elif op == "reverse":
            return pdf_tools.reverse_pages(input_path, output_path)
        elif op == "watermark":
            return pdf_tools.add_watermark(input_path, output_path, self.var_watermark_text.get())
        elif op == "pdf_to_img":
            return len(pdf_tools.pdf_to_images(input_path, output_path, self.var_dpi.get(), self.var_image_format.get())) > 0
        elif op == "split":
            return pdf_tools.split_pdf(input_path, output_path)
        elif op == "img_to_pdf":
            return pdf_tools.images_to_pdf([input_path], output_path)
        elif op == "ocr":
            # OCR - convert scanned PDF to searchable PDF
            try:
                from office_converter.utils.ocr import ocr_pdf_to_searchable, is_ocr_available
                if not is_ocr_available():
                    self.dialog.after(0, lambda: self._log("❌ OCR: Tesseract chưa được cài đặt"))
                    return False
                # Use lang=None for auto-detect available languages
                return ocr_pdf_to_searchable(input_path, output_path, lang=None)
            except ImportError:
                self.dialog.after(0, lambda: self._log("❌ OCR: Module OCR không khả dụng"))
                return False
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.dialog.after(0, lambda err=str(e): self._log(f"❌ OCR error: {err}"))
                return False
        return False
    
    def _on_done(self, success: int, total: int):
        """Handle processing completion."""
        self.is_processing = False
        self.btn_process.config(state="normal", bg="#4CAF50")
        self.btn_stop.config(state="disabled")
        self.lbl_status.config(text=f"✅ Xong: {success}/{total}")
        
        # Get output folder for "Open Folder" button
        if self.files:
            if self.var_output_same.get():
                output_folder = os.path.dirname(self.files[0])
            else:
                output_folder = self.var_output_folder.get() or os.path.dirname(self.files[0])
        else:
            output_folder = ""
        
        if success == total:
            self._show_success_dialog(f"Đã xử lý {success} files!", output_folder)
        elif success > 0:
            self._show_success_dialog(f"{success}/{total} files OK\nMột số file bị lỗi.", output_folder)
        else:
            messagebox.showerror("Lỗi", "Không xử lý được!")
    
    def _show_success_dialog(self, message: str, output_folder: str):
        """Show success dialog with Open Folder and Close buttons."""
        dialog = tk.Toplevel(self.dialog)
        dialog.title("Thành công")
        dialog.geometry("300x130")
        dialog.resizable(False, False)
        dialog.transient(self.dialog)
        dialog.grab_set()
        
        # Center on parent
        dialog.update_idletasks()
        x = self.dialog.winfo_x() + (self.dialog.winfo_width() - 300) // 2
        y = self.dialog.winfo_y() + (self.dialog.winfo_height() - 130) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Icon and message
        frame_msg = ttk.Frame(dialog, padding=15)
        frame_msg.pack(fill="both", expand=True)
        
        ttk.Label(frame_msg, text="✅", font=("", 24)).pack(side="left", padx=(0, 10))
        ttk.Label(frame_msg, text=message, wraplength=200).pack(side="left")
        
        # Buttons
        frame_btns = ttk.Frame(dialog, padding=10)
        frame_btns.pack(fill="x")
        
        def open_folder():
            if output_folder and os.path.exists(output_folder):
                os.startfile(output_folder)
            dialog.destroy()
        
        ttk.Button(frame_btns, text="📂 Mở Folder", command=open_folder, width=12).pack(side="left", padx=5)
        ttk.Button(frame_btns, text="Đóng", command=dialog.destroy, width=10).pack(side="right", padx=5)


def show_pdf_tools_dialog(parent, lang: str = "vi"):
    """Show the PDF Tools dialog."""
    PDFToolsDialog(parent, lang)
