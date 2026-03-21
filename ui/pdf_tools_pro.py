"""
PDF Tools Dialog Pro - Modern CustomTkinter interface for PDF operations
Professional UI with dark theme, smooth animations, and batch processing
"""

import os
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List
import logging

from office_converter.utils.config import Config
from office_converter.utils.localization import get_text
from office_converter.ui.pdf_tools_ops_mixin import PDFToolsOpsMixin

# Drag and drop support - TkinterDnD2 for robust Unicode handling
from office_converter.utils.tkdnd_wrapper import HAS_TKDND, DND_FILES
from office_converter.utils.dnd_helpers import parse_dropped_paths

if HAS_TKDND:
    logger_temp = logging.getLogger(__name__)
    logger_temp.info("tkinterdnd2 available for PDF Tools drag-drop")
else:
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("tkinterdnd2 not available in PDF Tools")

logger = logging.getLogger(__name__)


class PDFToolsDialogPro(ctk.CTkToplevel, PDFToolsOpsMixin):
    """Modern PDF Tools dialog with CustomTkinter.
    Processing logic in PDFToolsOpsMixin."""

    # Operation categories
    OPERATIONS = {
        "edit": [
            ("merge", "📎 Gộp PDF", "Gộp nhiều file thành 1"),
            ("split", get_text("op_split"), get_text("pt_split_desc")),
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
            ("smart_compress", get_text("pt_smart_compress"), get_text("pt_smart_desc")),
            ("protect", "🔒 Mật khẩu", "Bảo vệ bằng password"),
            ("watermark", "💧 Watermark", "Thêm watermark text"),
            ("rasterize", "🔐 Hóa ảnh (Secure)", "Flatten thành ảnh 1 lớp"),
            ("scanmode", "📠 Scan Mode", "Giả lập scan vật lý"),
        ],
    }

    # All operation keys for validation
    ALL_OPERATIONS = ["merge", "split", "extract", "delete", "rotate", "reverse",
                      "pdf_to_img", "img_to_pdf", "ocr", "compress", "smart_compress", "protect", "watermark", "rasterize", "scanmode"]

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
        self.geometry("1000x820")
        self.minsize(900, 700)

        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 1000) // 2
        y = (self.winfo_screenheight() - 750) // 2
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
        self.var_simulate_scan = ctk.BooleanVar(value=False)
        self.var_image_format = ctk.StringVar(value="png")
        self.var_combine_pages = ctk.BooleanVar(value=False)  # NEW: Combine all pages into single image
        self.var_custom_jpeg = ctk.StringVar(value="75")  # Custom JPEG quality (StringVar to avoid TclError)
        self.var_custom_dpi = ctk.StringVar(value="150")  # Custom DPI (StringVar to avoid TclError)
        self.var_target_kb = ctk.StringVar(value="1000")  # Target size in KB
        self.var_split_mode = ctk.StringVar(value="each_page")  # Split mode: each_page / by_parts / by_pages
        self.var_split_num = ctk.StringVar(value="3")  # Number for split modes
        self.var_output_same = ctk.BooleanVar(value=True)
        self.var_output_folder = ctk.StringVar()

        self._create_ui()

        # Set the correct tab based on last operation
        self._switch_to_operation_tab(last_op)

        # Non-modal: just keep on top of parent, don't lock input
        # This fixes the minimize/restore issue
        self.transient(parent)
        # Remove grab_set() to allow proper minimize/restore behavior
        # self.grab_set()  # Removed - causes minimize issues

        # Save operation when closing
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Bind Unmap (minimize) and Map (restore) events for state handling
        self.bind('<Unmap>', self._on_window_minimize)
        self.bind('<Map>', self._on_window_restore)
        self._is_minimized = False

    def _on_window_minimize(self, event=None):
        """Handle window minimize."""
        self._is_minimized = True

    def _on_window_restore(self, event=None):
        """Handle window restore after minimize."""
        if not self._is_minimized:
            return
        self._is_minimized = False
        
        try:
            # Force window to front and refresh
            self.deiconify()
            self.lift()
            self.focus_force()
            self.update_idletasks()
        except Exception:
            pass

    def _on_close(self):
        """Save last operation and close."""
        try:
            self.config.set("pdf_tools_last_operation", self.var_operation.get())
            self.config.save()
        except Exception as e:
            logger.error(f"Config save error: {e}")
        finally:
            self.grab_release()
            self.destroy()
            try:
                if self.parent:
                    self.parent.lift()
                    self.parent.focus_force()
            except Exception:
                pass

    def _switch_to_operation_tab(self, op: str):
        """Switch to the tab containing the given operation."""
        try:
            if op in ["merge", "split", "extract", "delete", "rotate", "reverse"]:
                self.tab_view.set(get_text("tab_edit"))
            elif op in ["pdf_to_img", "img_to_pdf", "ocr"]:
                self.tab_view.set("🔄 Chuyển đổi")
            elif op in ["compress", "smart_compress", "protect", "watermark", "rasterize", "scanmode"]:
                self.tab_view.set(get_text("tab_optimize"))
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
        self.tab_view = ctk.CTkTabview(left_panel, height=200)
        self.tab_view.pack(fill="x", padx=10, pady=(0, 10))

        # Create tabs
        tab_edit = self.tab_view.add(get_text("tab_edit"))
        tab_convert = self.tab_view.add("🔄 Chuyển đổi")
        tab_optimize = self.tab_view.add(get_text("tab_optimize"))

        # Populate tabs
        self._create_operation_buttons(tab_edit, self.OPERATIONS["edit"])
        self._create_operation_buttons(tab_convert, self.OPERATIONS["convert"])
        self._create_operation_buttons(tab_optimize, self.OPERATIONS["optimize"])

        # --- Options Panel ---
        self.options_frame = ctk.CTkFrame(left_panel)
        self.options_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            self.options_frame,
            text=get_text("options_title"),
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
            text=get_text("output_same"),
            variable=self.var_output_same,
            value=True
        ).pack(anchor="w", padx=15)

        other_row = ctk.CTkFrame(output_frame, fg_color="transparent")
        other_row.pack(fill="x", padx=15, pady=5)

        ctk.CTkRadioButton(
            other_row,
            text=get_text("output_custom"),
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
            text=get_text("btn_stop"),
            fg_color="#DC2626",
            hover_color="#B91C1C",
            width=100,
            state="disabled",
            command=self._stop_processing
        )
        self.btn_stop.pack(side="left")

        ctk.CTkButton(
            btn_row,
            text=get_text("btn_close"),
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
            (get_text("btn_add_file"), self._add_files),
            ("📁 Folder", self._add_folder),
            ("🗑️ Xóa", self._remove_files),
            ("🗑️ Hết", self._clear_files),
        ]:
            ctk.CTkButton(
                btn_frame, text=text, command=cmd,
                width=70, height=28
            ).pack(side="left", padx=2)

        # File list with selection support
        file_list_frame = ctk.CTkFrame(right_panel)
        file_list_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        file_list_frame.grid_rowconfigure(0, weight=1)
        file_list_frame.grid_columnconfigure(0, weight=1)

        # Use tk.Listbox for proper selection (Ctrl+A, Shift+arrows, Delete)
        self.file_listbox = tk.Listbox(
            file_list_frame,
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
        self.file_listbox.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        # Keyboard bindings for selection
        self.file_listbox.bind('<Control-a>', lambda e: self._select_all_files())
        self.file_listbox.bind('<Control-A>', lambda e: self._select_all_files())
        self.file_listbox.bind('<Delete>', lambda e: self._remove_selected_files())
        self.file_listbox.bind('<BackSpace>', lambda e: self._remove_selected_files())
        
        # Setup drag and drop for file list
        self._setup_file_drop(file_list_frame)

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
            text=get_text("status_ready"),
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
        # Safe clear: detach textvariables from CTkEntry before destroy
        # to prevent trace callbacks on dead widgets (CustomTkinter bug)
        for widget in self.options_content.winfo_children():
            try:
                # Recursively find all CTkEntry and detach textvariable
                for child in widget.winfo_children():
                    if hasattr(child, '_textvariable') and child._textvariable:
                        try:
                            child.configure(textvariable="")
                        except Exception:
                            pass
                    for grandchild in child.winfo_children():
                        if hasattr(grandchild, '_textvariable') and grandchild._textvariable:
                            try:
                                grandchild.configure(textvariable="")
                            except Exception:
                                pass
                widget.destroy()
            except Exception:
                pass

        op = self.var_operation.get()

        if op == "compress":
            ctk.CTkLabel(self.options_content, text="📊 Chất lượng nén:", font=("Segoe UI", 12, "bold")).pack(anchor="w")
            # Quality presets with expected reduction
            for val, text, desc in [
                ("extreme", "🔴 Cực mạnh (80-90%)", get_text("pt_q_extreme_desc")),
                ("low", "🟠 Mạnh (70-85%)", get_text("pt_q_low_desc")),
                ("medium", "🟡 Cân bằng (50-70%)", get_text("pt_q_medium_desc")),
                ("high", "🟢 Chất lượng (30-50%)", get_text("pt_q_high_desc")),
                ("lossless", get_text("pt_q_lossless"), get_text("pt_q_lossless_desc")),
                ("custom", get_text("pt_q_custom"), get_text("pt_q_custom_desc")),
                ("target_size", get_text("pt_q_target_size", "🎯 Dung lượng mục tiêu"), get_text("pt_q_target_desc", "Nén đến kích thước chỉ định")),
            ]:
                frame = ctk.CTkFrame(self.options_content, fg_color="transparent")
                frame.pack(fill="x", padx=5, pady=1)
                ctk.CTkRadioButton(
                    frame, text=text,
                    variable=self.var_quality, value=val, width=200,
                    command=self._update_options_panel
                ).pack(side="left")
                ctk.CTkLabel(frame, text=desc, text_color="gray", font=("Segoe UI", 10)).pack(side="left", padx=5)
            
            # Custom options (show when custom is selected)
            if self.var_quality.get() == "custom":
                custom_frame = ctk.CTkFrame(self.options_content, fg_color="#2b2b2b", corner_radius=8)
                custom_frame.pack(fill="x", padx=10, pady=3)
                
                # Single row: JPEG + DPI
                row = ctk.CTkFrame(custom_frame, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=6)
                ctk.CTkLabel(row, text="JPEG:", width=40).pack(side="left")
                ctk.CTkEntry(row, textvariable=self.var_custom_jpeg, width=45).pack(side="left")
                ctk.CTkLabel(row, text="%", text_color="gray", font=("Segoe UI", 9)).pack(side="left", padx=(2,10))
                ctk.CTkLabel(row, text="DPI:", width=30).pack(side="left")
                ctk.CTkEntry(row, textvariable=self.var_custom_dpi, width=45).pack(side="left")
                ctk.CTkLabel(row, text="(72-300)", text_color="gray", font=("Segoe UI", 9)).pack(side="left", padx=2)

            # Target Size Mode input (show when target_size is selected)
            if self.var_quality.get() == "target_size":
                target_frame = ctk.CTkFrame(self.options_content, fg_color="#1a3a2a", corner_radius=8)
                target_frame.pack(fill="x", padx=10, pady=3)
                
                row = ctk.CTkFrame(target_frame, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=4)
                ctk.CTkLabel(row, text=get_text("pt_target_kb_label", "Dung lượng tối đa:"),
                            font=("Segoe UI", 11)).pack(side="left")
                ctk.CTkEntry(row, textvariable=self.var_target_kb, width=70).pack(side="left", padx=5)
                ctk.CTkLabel(row, text="KB", text_color="#4da6ff",
                            font=("Segoe UI", 11, "bold")).pack(side="left")
                
                # File size hint + auto-search note on same line
                hint_parts = []
                if self.files:
                    try:
                        first_size = os.path.getsize(self.files[0]) / 1024
                        hint_parts.append(f"File: {first_size:.0f}KB")
                    except Exception:
                        pass
                hint_parts.append(get_text("pt_target_hint", "Auto binary search"))
                ctk.CTkLabel(row, text=" · ".join(hint_parts),
                            text_color="#4ade80", font=("Segoe UI", 9)).pack(side="left", padx=(10, 0))

        elif op == "smart_compress":
            # Smart compression - preserves text layer
            ctk.CTkLabel(self.options_content, text=get_text("pt_smart_title"),
                        font=("Segoe UI", 12, "bold")).pack(anchor="w")
            ctk.CTkLabel(self.options_content, 
                        text=get_text("pt_smart_features"),
                        text_color="#4da6ff", font=("Segoe UI", 10), justify="left").pack(anchor="w", pady=5)
            
            ctk.CTkLabel(self.options_content, text=get_text("pt_image_quality"), font=("Segoe UI", 11)).pack(anchor="w", pady=(5,0))
            for val, text in [
                ("low", get_text("pt_sq_low")),
                ("medium", get_text("pt_sq_medium")),
                ("high", get_text("pt_sq_high")),
            ]:
                ctk.CTkRadioButton(
                    self.options_content, text=text,
                    variable=self.var_quality, value=val
                ).pack(anchor="w", padx=10, pady=1)

        elif op == "split":
            ctk.CTkLabel(self.options_content, text="✂️ Chế độ tách:",
                        font=("Segoe UI", 12, "bold")).pack(anchor="w")
            
            for val, text in [
                ("each_page", get_text("pt_split_each", "📄 Mỗi trang → 1 file")),
                ("by_parts", get_text("pt_split_parts", "📦 Tách thành N file")),
                ("by_pages", get_text("pt_split_pages", "📑 Mỗi file N trang")),
            ]:
                ctk.CTkRadioButton(
                    self.options_content, text=text,
                    variable=self.var_split_mode, value=val,
                    command=self._update_options_panel,
                ).pack(anchor="w", padx=10, pady=2)
            
            mode = self.var_split_mode.get()
            if mode in ("by_parts", "by_pages"):
                input_frame = ctk.CTkFrame(self.options_content, fg_color="#1a2a3a", corner_radius=8)
                input_frame.pack(fill="x", padx=10, pady=5)
                
                row = ctk.CTkFrame(input_frame, fg_color="transparent")
                row.pack(fill="x", padx=8, pady=4)
                
                if mode == "by_parts":
                    label = get_text("pt_split_num_parts", "Số file cần tách:")
                else:
                    label = get_text("pt_split_num_pages", "Số trang mỗi file:")
                
                ctk.CTkLabel(row, text=label, font=("Segoe UI", 11)).pack(side="left")
                ctk.CTkEntry(row, textvariable=self.var_split_num, width=50).pack(side="left", padx=5)
                
                # Page count hint
                if self.files:
                    try:
                        import fitz as fitz_mod
                        doc = fitz_mod.open(self.files[0])
                        pc = len(doc)
                        doc.close()
                        if mode == "by_parts":
                            try:
                                n = max(1, int(self.var_split_num.get()))
                                import math
                                ppf = math.ceil(pc / n)
                                hint = f"{pc} trang ÷ {n} file ≈ {ppf} trang/file"
                            except ValueError:
                                hint = f"{pc} trang"
                        else:
                            try:
                                n = max(1, int(self.var_split_num.get()))
                                import math
                                parts = math.ceil(pc / n)
                                hint = f"{pc} trang ÷ {n} = {parts} file"
                            except ValueError:
                                hint = f"{pc} trang"
                        ctk.CTkLabel(row, text=hint, text_color="#4ade80",
                                    font=("Segoe UI", 9)).pack(side="left", padx=8)
                    except Exception:
                        pass

        elif op == "rotate":
            ctk.CTkLabel(self.options_content, text=get_text("rotation_angle")).pack(anchor="w")
            for val in [90, 180, 270]:
                ctk.CTkRadioButton(
                    self.options_content, text=f"{val}°",
                    variable=self.var_rotation, value=val
                ).pack(anchor="w", padx=10)

        elif op in ["extract", "delete"]:
            ctk.CTkLabel(self.options_content, text=get_text("page_range_hint")).pack(anchor="w")
            ctk.CTkEntry(
                self.options_content,
                textvariable=self.var_page_range,
                width=200
            ).pack(anchor="w", pady=5)

        elif op == "watermark":
            ctk.CTkLabel(self.options_content, text=get_text("watermark_text")).pack(anchor="w")
            ctk.CTkEntry(
                self.options_content,
                textvariable=self.var_watermark_text,
                width=200
            ).pack(anchor="w", pady=5)

        elif op == "protect":
            ctk.CTkLabel(self.options_content, text=get_text("password_label")).pack(anchor="w")
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

            ctk.CTkLabel(self.options_content, text=get_text("format_label")).pack(anchor="w")
            for fmt in ["png", "jpg"]:
                ctk.CTkRadioButton(
                    self.options_content, text=fmt.upper(),
                    variable=self.var_image_format, value=fmt
                ).pack(anchor="w", padx=10)
            
            # NEW: Combine pages option
            ctk.CTkCheckBox(
                self.options_content,
                text=get_text("pt_combine_pages"),
                variable=self.var_combine_pages
            ).pack(anchor="w", pady=(10, 0))
            ctk.CTkLabel(
                self.options_content,
                text=get_text("pt_combine_hint"),
                text_color="gray",
                font=ctk.CTkFont(size=10)
            ).pack(anchor="w", padx=25)

        elif op == "rasterize":
            ctk.CTkLabel(self.options_content, text=get_text("pt_rasterize_quality")).pack(anchor="w")
            ctk.CTkLabel(
                self.options_content, 
                text=get_text("pt_rasterize_warn"),
                text_color="#F59E0B",
                font=ctk.CTkFont(size=11)
            ).pack(anchor="w", pady=(0, 5))
            
            ctk.CTkSlider(
                self.options_content,
                from_=72, to=300,
                variable=self.var_dpi,
                width=180
            ).pack(anchor="w", pady=5)
            
            # Show DPI value
            self.lbl_dpi = ctk.CTkLabel(self.options_content, text=f"{self.var_dpi.get()} DPI")
            self.lbl_dpi.pack(anchor="w", padx=5)
            
            def update_dpi_label(value):
                self.lbl_dpi.configure(text=f"{int(value)} DPI")
                
            self.var_dpi.trace_add("write", lambda *args: update_dpi_label(self.var_dpi.get()))

            # Checkbox simulate scan
            ctk.CTkCheckBox(
                self.options_content,
                text="Hiệu ứng Scan thật (Grayscale + Noise)",
                variable=self.var_simulate_scan,
                font=ctk.CTkFont(size=12)
            ).pack(anchor="w", pady=5)

        elif op == "scanmode":
            ctk.CTkLabel(
                self.options_content,
                text="📠 Chuyển PDF thành dạng scan",
                font=ctk.CTkFont(weight="bold")
            ).pack(anchor="w", pady=(0, 5))
            
            ctk.CTkLabel(
                self.options_content,
                text="✓ Grayscale + Noise + Blur + Xoay nhẹ",
                text_color="#10B981",
                font=ctk.CTkFont(size=11)
            ).pack(anchor="w")
            
            ctk.CTkLabel(
                self.options_content,
                text="⚠️ Không thể copy text sau khi convert",
                text_color="#F59E0B",
                font=ctk.CTkFont(size=11)
            ).pack(anchor="w", pady=(0, 10))
            
            ctk.CTkLabel(self.options_content, text="Chất lượng (DPI):").pack(anchor="w")
            self.var_scan_dpi = ctk.IntVar(value=150)
            dpi_frame = ctk.CTkFrame(self.options_content, fg_color="transparent")
            dpi_frame.pack(anchor="w", fill="x")
            
            for dpi, label in [(100, "Nhanh"), (150, "Chuẩn"), (200, "Cao")]:
                ctk.CTkRadioButton(
                    dpi_frame, text=f"{label} ({dpi})",
                    variable=self.var_scan_dpi, value=dpi
                ).pack(side="left", padx=5)

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
        """Remove selected files."""
        self._remove_selected_files()

    def _remove_selected_files(self):
        """Remove selected files from list."""
        selection = self.file_listbox.curselection()
        if not selection:
            # If nothing selected, remove last one
            if self.files:
                self.files.pop()
        else:
            # Remove in reverse order to maintain indices
            for idx in sorted(selection, reverse=True):
                if 0 <= idx < len(self.files):
                    del self.files[idx]
        self._refresh_file_list()
        return "break"

    def _select_all_files(self):
        """Select all files in the list."""
        if self.files:
            self.file_listbox.select_set(0, tk.END)
        return "break"

    def _clear_files(self):
        """Clear all files."""
        self.files.clear()
        self.compression_results.clear()
        self._refresh_file_list()

    def _setup_file_drop(self, frame):
        """Setup drag and drop using TkinterDnD2 with Unicode support."""
        if not HAS_TKDND:
            logger.info("windnd not available, drag drop disabled in PDF Tools")
            return
            
        try:
            # Register the dialog window for drag and drop
            self.drop_target_register(DND_FILES)
            # Bind drop event
            self.dnd_bind('<<Drop>>', self._handle_drop_event)
            logger.info("Drag and drop enabled for PDF Tools (TkinterDnD2)")
        except Exception as e:
            logger.warning(f"Could not setup drag & drop: {e}")

    def _handle_drop_event(self, event):
        """Handle dropped files with robust Unicode path parsing via tk.splitlist()."""
        try:
            if not event.data:
                return
            
            # Parse paths using production-grade utility
            file_paths = parse_dropped_paths(self, event.data)
            
            if not file_paths:
                logger.warning("No valid files in drop event")
                return
            
            op = self.var_operation.get()
            valid_exts = {'.png', '.jpg', '.jpeg', '.bmp', '.gif'} if op == "img_to_pdf" else {'.pdf'}
            
            added = 0
            for file_path in file_paths:
                try:
                    # Check extension
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in valid_exts and file_path not in self.files:
                        self.files.append(file_path)
                        added += 1
                except Exception:
                    continue
            
            if added > 0:
                self._refresh_file_list()
                self._log(f"📁 Thả thêm {added} file(s)")
        except Exception as e:
            logger.error(f"Drop error: {e}")

    def _refresh_file_list(self):
        """Refresh the file list display."""
        # Clear and repopulate listbox
        self.file_listbox.delete(0, tk.END)

        for i, f in enumerate(self.files, 1):
            basename = os.path.basename(f)
            try:
                size = os.path.getsize(f) / 1024  # KB
            except Exception:
                size = 0

            # Show compression results if available
            if f in self.compression_results:
                orig, new = self.compression_results[f]
                ratio = (1 - new/orig) * 100 if orig > 0 else 0
                line = f"{i}. {basename} ({size:.0f}KB → {new/1024:.0f}KB, -{ratio:.0f}%)"
            else:
                line = f"{i}. {basename} ({size:.0f} KB)"

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

    # Processing methods (_process_files, _execute_operation, _do_merge, _on_done)
    # are inherited from PDFToolsOpsMixin


def show_pdf_tools_pro(parent, lang: str = "vi"):
    """Show the PDF Tools Pro dialog."""
    PDFToolsDialogPro(parent, lang)
