"""
File Tools UI V2 - 3 Tab Vietnamese Interface
Based on user reference design with:
- Tab 1: Rename cơ bản (Basic Rename)
- Tab 2: Rename nâng cao (Advanced Rename)
- Tab 3: Các chức năng khác (Other Functions)
"""
from tkinter import filedialog, messagebox
import customtkinter as ctk
import os
import threading
from typing import List

from office_converter.core.file_tools import (
    FileToolsEngine, CaseRule, ReplaceRule, RemoveAccentsRule,
    TrimRule, AddStringRule, SequenceRule, ExtensionRule, RenameRule,
    DuplicateFinder
)

import logging
logger = logging.getLogger(__name__)


class FileToolsDialogV2(ctk.CTkToplevel):
    """File Tools Dialog with 3-Tab Vietnamese Interface."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📁 File Tools Pro")
        self.geometry("950x650")
        self.minsize(850, 550)
        
        # Engine
        self.engine = FileToolsEngine()
        self.dup_finder = DuplicateFinder()
        self.files: List[str] = []
        
        # Variables for Tab 1 (Basic)
        self.var_basic_mode = ctk.StringVar(value="title")
        self.var_trim_whitespace = ctk.BooleanVar(value=True)
        self.var_new_extension = ctk.StringVar()
        
        # Variables for Tab 2 (Advanced)
        self.var_replace_find = ctk.StringVar()
        self.var_replace_with = ctk.StringVar()
        self.var_cut_pos = ctk.StringVar(value="start")
        self.var_cut_count = ctk.StringVar()
        self.var_cut_after = ctk.StringVar()
        self.var_add_text = ctk.StringVar()
        self.var_add_pos = ctk.StringVar(value="start")
        
        # Variables for Tab 3 (Other)
        self.var_numbering = ctk.StringVar(value="none")
        
        # Common variables
        self.var_include_subdir = ctk.BooleanVar(value=False)
        self.var_remove_accents = ctk.BooleanVar(value=False)
        self.var_open_after = ctk.BooleanVar(value=True)
        self.var_save_log = ctk.BooleanVar(value=False)
        
        self._create_ui()
        
    def _create_ui(self):
        """Build the main UI."""
        # Main container
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top: Folder selector
        self._create_folder_selector(main_frame)
        
        # Middle: Left (Tabs) + Right (File lists)
        content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, pady=10)
        
        # Left panel - Tabs
        left_panel = ctk.CTkFrame(content_frame, width=400)
        left_panel.pack(side="left", fill="both", padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self._create_tabs(left_panel)
        
        # Right panel - File lists
        right_panel = ctk.CTkFrame(content_frame)
        right_panel.pack(side="right", fill="both", expand=True)
        
        self._create_file_lists(right_panel)
        
        # Bottom: Action buttons
        self._create_footer(main_frame)
        
    def _create_folder_selector(self, parent):
        """Create folder path input."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x")
        
        self.entry_path = ctk.CTkEntry(frame, placeholder_text="Chọn thư mục chứa file cần đổi tên...")
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        btn_browse = ctk.CTkButton(frame, text="Chọn đường dẫn", width=120, command=self._browse_folder)
        btn_browse.pack(side="right")
        
    def _create_tabs(self, parent):
        """Create 3-tab notebook."""
        self.tabview = ctk.CTkTabview(parent)
        self.tabview.pack(fill="both", expand=True)
        
        # Add tabs
        self.tab1 = self.tabview.add("Rename cơ bản")
        self.tab2 = self.tabview.add("Rename nâng cao")
        self.tab3 = self.tabview.add("Các chức năng khác")
        
        self._create_tab1_basic(self.tab1)
        self._create_tab2_advanced(self.tab2)
        self._create_tab3_other(self.tab3)
        
    def _create_tab1_basic(self, parent):
        """Tab 1: Basic rename options."""
        # Radio options frame
        options_frame = ctk.CTkFrame(parent, fg_color="transparent")
        options_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Row 1
        row1 = ctk.CTkFrame(options_frame, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkRadioButton(row1, text="Viết Hoa Chữ Đầu", variable=self.var_basic_mode, value="title").pack(side="left", padx=10)
        ctk.CTkRadioButton(row1, text="VIẾT HOA TOÀN BỘ", variable=self.var_basic_mode, value="upper").pack(side="left", padx=10)
        
        # Row 2
        row2 = ctk.CTkFrame(options_frame, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkRadioButton(row2, text="viết thường toàn bộ", variable=self.var_basic_mode, value="lower").pack(side="left", padx=10)
        ctk.CTkRadioButton(row2, text="Chỉ viết hoa chữ cái đầu tiên", variable=self.var_basic_mode, value="capitalize").pack(side="left", padx=10)
        
        # Row 3
        row3 = ctk.CTkFrame(options_frame, fg_color="transparent")
        row3.pack(fill="x", pady=2)
        ctk.CTkRadioButton(row3, text="Loại Bỏ Khoảng Trắng", variable=self.var_basic_mode, value="remove_spaces").pack(side="left", padx=10)
        ctk.CTkRadioButton(row3, text="Bỏ toàn bộ tên cũ thay bằng số", variable=self.var_basic_mode, value="number_only").pack(side="left", padx=10)
        
        # Row 4
        row4 = ctk.CTkFrame(options_frame, fg_color="transparent")
        row4.pack(fill="x", pady=2)
        ctk.CTkRadioButton(row4, text="Phục Hồi Khoảng Trắng", variable=self.var_basic_mode, value="restore_spaces").pack(side="left", padx=10)
        
        # Checkbox
        ctk.CTkCheckBox(options_frame, text="Bỏ khoảng trắng ở đầu và cuối", variable=self.var_trim_whitespace).pack(anchor="w", padx=10, pady=10)
        
        # Extension change
        ext_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        ext_frame.pack(fill="x", pady=5, padx=10)
        ctk.CTkLabel(ext_frame, text="Đổi đuôi thành:").pack(side="left")
        ctk.CTkEntry(ext_frame, textvariable=self.var_new_extension, width=80, placeholder_text=".txt").pack(side="left", padx=10)
        
    def _create_tab2_advanced(self, parent):
        """Tab 2: Advanced rename options."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Replace section
        replace_frame = ctk.CTkFrame(frame, fg_color="transparent")
        replace_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(replace_frame, text="Thay thế").pack(side="left", padx=5)
        ctk.CTkEntry(replace_frame, textvariable=self.var_replace_find, width=100, placeholder_text="Tìm...").pack(side="left", padx=5)
        ctk.CTkLabel(replace_frame, text="Bằng").pack(side="left", padx=5)
        ctk.CTkEntry(replace_frame, textvariable=self.var_replace_with, width=100, placeholder_text="Thay bằng...").pack(side="left", padx=5)
        
        # Cut section
        cut_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cut_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(cut_frame, text="Cắt từ").pack(side="left", padx=5)
        ctk.CTkRadioButton(cut_frame, text="Đầu", variable=self.var_cut_pos, value="start").pack(side="left", padx=5)
        ctk.CTkRadioButton(cut_frame, text="Cuối", variable=self.var_cut_pos, value="end").pack(side="left", padx=5)
        ctk.CTkLabel(cut_frame, text="Lấy").pack(side="left", padx=5)
        ctk.CTkEntry(cut_frame, textvariable=self.var_cut_count, width=50, placeholder_text="N").pack(side="left", padx=5)
        ctk.CTkLabel(cut_frame, text="kí tự").pack(side="left")
        
        # Cut after delimiter
        cutafter_frame = ctk.CTkFrame(frame, fg_color="transparent")
        cutafter_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(cutafter_frame, text="Cắt bỏ phần sau bắt đầu bằng kí tự:").pack(side="left", padx=5)
        ctk.CTkEntry(cutafter_frame, textvariable=self.var_cut_after, width=80).pack(side="left", padx=5)
        
        # Add text section
        add_frame = ctk.CTkFrame(frame, fg_color="transparent")
        add_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(add_frame, text="Thêm từ").pack(side="left", padx=5)
        ctk.CTkEntry(add_frame, textvariable=self.var_add_text, width=120).pack(side="left", padx=5)
        ctk.CTkRadioButton(add_frame, text="Vào đầu", variable=self.var_add_pos, value="start").pack(side="left", padx=10)
        ctk.CTkRadioButton(add_frame, text="Vào cuối", variable=self.var_add_pos, value="end").pack(side="left", padx=10)
        
    def _create_tab3_other(self, parent):
        """Tab 3: Other functions."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left buttons
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(side="left", fill="y", padx=10)
        
        ctk.CTkButton(btn_frame, text="Xóa chi tiết", width=150, command=self._clear_details).pack(pady=3)
        ctk.CTkButton(btn_frame, text="Copy tên file vào title", width=150).pack(pady=3)
        ctk.CTkButton(btn_frame, text="Copy tên title sang tên file", width=150).pack(pady=3)
        ctk.CTkButton(btn_frame, text="Check mã MD5 hàng loạt", width=150, command=self._check_md5).pack(pady=3)
        ctk.CTkButton(btn_frame, text="So sánh 2 thư mục", width=150).pack(pady=3)
        ctk.CTkButton(btn_frame, text="Tìm file trùng", width=150, command=self._find_duplicates).pack(pady=3)
        
        # Right numbering options
        num_frame = ctk.CTkFrame(frame, fg_color="transparent")
        num_frame.pack(side="right", fill="both", expand=True, padx=10)
        
        ctk.CTkLabel(num_frame, text="Đánh số thứ tự", font=ctk.CTkFont(weight="bold")).pack(anchor="w")
        
        ctk.CTkRadioButton(num_frame, text="Không", variable=self.var_numbering, value="none").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(num_frame, text="Ở đầu file", variable=self.var_numbering, value="prefix").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(num_frame, text="Ở cuối file", variable=self.var_numbering, value="suffix").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(num_frame, text="Bỏ toàn bộ stt ở đầu file", variable=self.var_numbering, value="remove_prefix").pack(anchor="w", pady=2)
        ctk.CTkRadioButton(num_frame, text="Bỏ toàn bộ stt ở cuối file", variable=self.var_numbering, value="remove_suffix").pack(anchor="w", pady=2)
        
    def _create_file_lists(self, parent):
        """Create old name / new name file lists."""
        # Header
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(header, text="Tên cũ", font=ctk.CTkFont(weight="bold")).pack(side="left", expand=True)
        ctk.CTkButton(header, text="Refresh", width=60, command=self._refresh_files).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Tên mới", font=ctk.CTkFont(weight="bold")).pack(side="right", expand=True)
        
        # Lists container
        lists_frame = ctk.CTkFrame(parent, fg_color="transparent")
        lists_frame.pack(fill="both", expand=True, pady=5)
        
        # Old names list
        self.list_old = ctk.CTkTextbox(lists_frame, width=200)
        self.list_old.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # New names list
        self.list_new = ctk.CTkTextbox(lists_frame, width=200)
        self.list_new.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
    def _create_footer(self, parent):
        """Create bottom action buttons."""
        # Checkboxes row
        cb_frame = ctk.CTkFrame(parent, fg_color="transparent")
        cb_frame.pack(fill="x", pady=5)
        
        ctk.CTkCheckBox(cb_frame, text="Bao gồm thư mục con", variable=self.var_include_subdir).pack(side="left", padx=10)
        ctk.CTkCheckBox(cb_frame, text="Loại bỏ dấu", variable=self.var_remove_accents).pack(side="left", padx=10)
        
        # Buttons row
        btn_frame = ctk.CTkFrame(parent, fg_color="transparent")
        btn_frame.pack(fill="x", pady=5)
        
        ctk.CTkButton(btn_frame, text="Undo", width=80, fg_color="#6B7280", command=self._undo).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Reset form", width=80, fg_color="#6B7280", command=self._reset_form).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Phóng to kết quả", width=120, fg_color="#3B82F6").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Xuất kết quả ra txt", width=120, fg_color="#3B82F6").pack(side="left", padx=5)
        
        # Right side
        ctk.CTkButton(btn_frame, text="Rename!", width=100, fg_color="#10B981", hover_color="#059669", command=self._execute_rename).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Xem thử trước", width=100, fg_color="#F59E0B", hover_color="#D97706", command=self._preview).pack(side="right", padx=5)
        
        # Bottom checkboxes
        bottom_frame = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_frame.pack(fill="x")
        
        ctk.CTkCheckBox(bottom_frame, text="Mở thư mục khi kết thúc", variable=self.var_open_after).pack(side="left", padx=10)
        ctk.CTkCheckBox(bottom_frame, text="Lưu lại log file", variable=self.var_save_log).pack(side="left", padx=10)
        
    # ===================== Actions =====================
    
    def _browse_folder(self):
        """Open folder dialog."""
        folder = filedialog.askdirectory()
        if folder:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, folder)
            self._load_files(folder)
            
    def _load_files(self, folder: str):
        """Load files from folder."""
        self.files = []
        include_sub = self.var_include_subdir.get()
        
        if include_sub:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    self.files.append(os.path.join(root, f))
        else:
            for f in os.listdir(folder):
                path = os.path.join(folder, f)
                if os.path.isfile(path):
                    self.files.append(path)
        
        self._update_file_lists()
        
    def _update_file_lists(self):
        """Update old and new name lists."""
        self.list_old.delete("1.0", "end")
        for f in self.files:
            self.list_old.insert("end", os.path.basename(f) + "\n")
            
    def _refresh_files(self):
        """Refresh file list."""
        folder = self.entry_path.get()
        if folder and os.path.isdir(folder):
            self._load_files(folder)
            
    def _build_rules(self) -> List[RenameRule]:
        """Build rules from current UI state."""
        rules = []
        
        # Basic mode
        mode = self.var_basic_mode.get()
        if mode in ["lower", "upper", "title", "capitalize"]:
            rules.append(CaseRule(mode))
        elif mode == "remove_spaces":
            rules.append(ReplaceRule(" ", ""))
        elif mode == "restore_spaces":
            rules.append(ReplaceRule("_", " "))
        elif mode == "number_only":
            # Special: will be handled in execute
            pass
            
        # Trim whitespace
        if self.var_trim_whitespace.get():
            rules.append(TrimRule())
            
        # Remove accents
        if self.var_remove_accents.get():
            rules.append(RemoveAccentsRule())
            
        # Replace
        find = self.var_replace_find.get()
        replace = self.var_replace_with.get()
        if find:
            rules.append(ReplaceRule(find, replace))
            
        # Add text
        add_text = self.var_add_text.get()
        if add_text:
            at_start = (self.var_add_pos.get() == "start")
            rules.append(AddStringRule(add_text, at_start))
            
        # Extension
        new_ext = self.var_new_extension.get()
        if new_ext:
            if not new_ext.startswith("."):
                new_ext = "." + new_ext
            rules.append(ExtensionRule("new", new_ext))
            
        # Numbering
        num_mode = self.var_numbering.get()
        if num_mode == "prefix":
            rules.append(SequenceRule(position="prefix"))
        elif num_mode == "suffix":
            rules.append(SequenceRule(position="suffix"))
            
        return rules
        
    def _preview(self):
        """Preview rename results."""
        if not self.files:
            messagebox.showwarning("Cảnh báo", "Chưa chọn thư mục!")
            return
            
        rules = self._build_rules()
        self.engine.rules = rules
        
        previews = self.engine.preview(self.files)
        
        self.list_new.delete("1.0", "end")
        for p in previews:
            status = "✓" if p.status == "ok" else "⚠"
            self.list_new.insert("end", f"{status} {p.new_filename}\n")
            
    def _execute_rename(self):
        """Execute rename operation."""
        if not self.files:
            messagebox.showwarning("Cảnh báo", "Chưa chọn thư mục!")
            return
            
        rules = self._build_rules()
        self.engine.rules = rules
        
        results = self.engine.execute(self.files)
        
        success = sum(1 for _, s, _ in results if s)
        failed = len(results) - success
        
        messagebox.showinfo("Kết quả", f"Thành công: {success}\nThất bại: {failed}")
        
        if self.var_open_after.get():
            folder = self.entry_path.get()
            if folder:
                os.startfile(folder)
                
    def _undo(self):
        """Undo last rename operation."""
        results = self.engine.undo()
        if results:
            success = sum(1 for _, s, _ in results if s)
            messagebox.showinfo("Undo", f"Đã hoàn tác {success} file")
        else:
            messagebox.showinfo("Undo", "Không có gì để hoàn tác")
            
    def _reset_form(self):
        """Reset all form fields."""
        self.var_basic_mode.set("title")
        self.var_trim_whitespace.set(True)
        self.var_new_extension.set("")
        self.var_replace_find.set("")
        self.var_replace_with.set("")
        self.var_add_text.set("")
        self.var_numbering.set("none")
        self.var_remove_accents.set(False)
        self.list_new.delete("1.0", "end")
        
    def _clear_details(self):
        """Clear detail info - placeholder."""
        messagebox.showinfo("Info", "Chức năng đang phát triển")
        
    def _check_md5(self):
        """Check MD5 hashes."""
        if not self.files:
            messagebox.showwarning("Cảnh báo", "Chưa chọn thư mục!")
            return
        # TODO: Implement MD5 check
        messagebox.showinfo("Info", "Chức năng đang phát triển")
        
    def _find_duplicates(self):
        """Find duplicate files."""
        folder = self.entry_path.get()
        if not folder:
            messagebox.showwarning("Cảnh báo", "Chưa chọn thư mục!")
            return
            
        def run_scan():
            groups = self.dup_finder.find_duplicates([folder])
            self.after(0, lambda: self._show_duplicates(groups))
            
        threading.Thread(target=run_scan, daemon=True).start()
        messagebox.showinfo("Info", "Đang quét file trùng...")
        
    def _show_duplicates(self, groups):
        """Show duplicate results."""
        if not groups:
            messagebox.showinfo("Kết quả", "Không tìm thấy file trùng!")
        else:
            total = sum(len(g.files) for g in groups)
            messagebox.showinfo("Kết quả", f"Tìm thấy {len(groups)} nhóm ({total} files)")


# Keep backward compatibility
FileToolsDialog = FileToolsDialogV2
