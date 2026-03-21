"""
UI for File Tools (Rename, etc).
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import os
import threading
from typing import List

from office_converter.core.file_tools import (
    FileToolsEngine, CaseRule, ReplaceRule, RemoveAccentsRule,
    TrimRule, AddStringRule, SequenceRule, ExtensionRule, RenameRule,
    DuplicateFinder, DuplicateGroup, EmptyFolderCleaner, AttributeManager
)
import time

class DuplicateResultWidget(ctk.CTkFrame):
    """Widget for duplicate group."""
    def __init__(self, parent, group: DuplicateGroup, on_open):
        super().__init__(parent, fg_color="transparent")
        self.group = group
        self.on_open = on_open
        self.vars = []
        
        # Header (Size + Hash)
        size_str = f"{group.size} bytes"
        if group.size > 1024: size_str = f"{group.size/1024:.1f} KB"
        if group.size > 1024*1024: size_str = f"{group.size/(1024*1024):.1f} MB"
        
        header = ctk.CTkLabel(
            self, 
            text=f"Group ({len(group.files)} files) - {size_str} - {group.hash_val[:8]}...", 
            font=ctk.CTkFont(weight="bold")
        )
        header.pack(anchor="w", padx=5)
        
        # Files list
        for f in group.files:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=20)
            
            var = ctk.BooleanVar(value=False)
            self.vars.append((var, f))
            
            cb = ctk.CTkCheckBox(row, text=os.path.basename(f), variable=var, width=20)
            cb.pack(side="left")
            
            # Open button
            btn = ctk.CTkButton(
                row, text="Open", width=40, height=20, 
                font=ctk.CTkFont(size=10),
                command=lambda p=f: on_open(p)
            )
            btn.pack(side="right")
            
            # Path tooltip/label
            path_lbl = ctk.CTkLabel(row, text=os.path.dirname(f), text_color="gray", font=ctk.CTkFont(size=10))
            path_lbl.pack(side="left", padx=10)

class RuleWidget(ctk.CTkFrame):
    """Widget representing a single rule in the stack."""
    def __init__(self, parent, rule: RenameRule, on_remove, on_change):
        super().__init__(parent, fg_color="#374151", corner_radius=6)
        self.rule = rule
        self.on_remove = on_remove
        self.on_change = on_change
        
        # Rule Name
        self.lbl_name = ctk.CTkLabel(
            self, 
            text=rule.description, 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.lbl_name.pack(side="left", padx=10, pady=5)
        
        # Helper frame for controls
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.pack(side="right", padx=5)

        # Move Up
        self.btn_up = ctk.CTkButton(
            ctrl_frame, text="▲", width=20, height=20,
            fg_color="#4B5563", hover_color="#374151",
            command=lambda: on_change(self, "up")
        )
        self.btn_up.pack(side="left", padx=1)
        
        # Move Down
        self.btn_down = ctk.CTkButton(
            ctrl_frame, text="▼", width=20, height=20,
            fg_color="#4B5563", hover_color="#374151",
            command=lambda: on_change(self, "down")
        )
        self.btn_down.pack(side="left", padx=1)

        # Remove Button
        self.btn_remove = ctk.CTkButton(
            ctrl_frame,
            text="✕",
            width=20,
            height=20,
            fg_color="transparent",
            text_color="#EF4444",
            hover_color="#374151",
            command=lambda: on_change(self, "remove")
        )
        self.btn_remove.pack(side="left", padx=1)
        
        # Config options container
        self.config_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.config_frame.pack(fill="x", padx=10, pady=5)
        
        self._create_config_ui()
        
    def _create_config_ui(self):
        """Create specific config widgets based on rule type."""
        r = self.rule
        
        if isinstance(r, CaseRule):
            modes = ["lower", "upper", "title", "capitalize"]
            cb = ctk.CTkComboBox(
                self.config_frame, 
                values=modes,
                command=self._on_config_change,
                width=100
            )
            cb.set(r.mode)
            cb.pack(side="left")
            self.widgets = {"mode": cb}
            
        elif isinstance(r, ReplaceRule):
            ctk.CTkLabel(self.config_frame, text="Find:").pack(side="left")
            e1 = ctk.CTkEntry(self.config_frame, width=80)
            e1.insert(0, r.old)
            e1.pack(side="left", padx=2)
            e1.bind("<KeyRelease>", self._on_config_change)
            
            ctk.CTkLabel(self.config_frame, text="Replace:").pack(side="left")
            e2 = ctk.CTkEntry(self.config_frame, width=80)
            e2.insert(0, r.new)
            e2.pack(side="left", padx=2)
            e2.bind("<KeyRelease>", self._on_config_change)
            self.widgets = {"find": e1, "replace": e2}
            
        elif isinstance(r, AddStringRule):
            ctk.CTkLabel(self.config_frame, text="Text:").pack(side="left")
            e1 = ctk.CTkEntry(self.config_frame, width=100)
            e1.insert(0, r.text)
            e1.pack(side="left", padx=2)
            e1.bind("<KeyRelease>", self._on_config_change)
            
            # Position (Start/End) - tricky with variable in customtk, using simple logic
            self.pos_var = ctk.StringVar(value="start" if r.at_start else "end")
            r1 = ctk.CTkRadioButton(self.config_frame, text="Start", variable=self.pos_var, value="start", command=self._on_config_change)
            r2 = ctk.CTkRadioButton(self.config_frame, text="End", variable=self.pos_var, value="end", command=self._on_config_change)
            r1.pack(side="left", padx=5)
            r2.pack(side="left")
            
            self.widgets = {"text": e1}
            
        elif isinstance(r, ExtensionRule):
            modes = ["preserve", "lower", "upper", "new"]
            cb = ctk.CTkComboBox(
                self.config_frame, 
                values=modes,
                command=self._on_config_change,
                width=100
            )
            cb.set(r.mode)
            cb.pack(side="left", padx=2)
            
            e1 = ctk.CTkEntry(self.config_frame, placeholder_text=".txt", width=60)
            e1.insert(0, r.new_ext)
            e1.pack(side="left", padx=2)
            e1.bind("<KeyRelease>", self._on_config_change)
            
            self.widgets = {"mode": cb, "ext": e1}
            
        elif isinstance(r, SequenceRule):
            ctk.CTkLabel(self.config_frame, text="Start:").pack(side="left")
            e1 = ctk.CTkEntry(self.config_frame, width=40)
            e1.insert(0, str(r.start))
            e1.pack(side="left", padx=2)
            e1.bind("<KeyRelease>", self._on_config_change)
            
            ctk.CTkLabel(self.config_frame, text="Step:").pack(side="left")
            e2 = ctk.CTkEntry(self.config_frame, width=40)
            e2.insert(0, str(r.step))
            e2.pack(side="left", padx=2)
            e2.bind("<KeyRelease>", self._on_config_change)
            
            self.widgets = {"start": e1, "step": e2}

    def _on_config_change(self, event=None):
        """Update rule object from widgets."""
        r = self.rule
        
        try:
            if isinstance(r, CaseRule):
                r.mode = self.widgets["mode"].get()
                r.description # Update desc if dynamic? No dynamic update needed for now
                
            elif isinstance(r, ReplaceRule):
                r.old = self.widgets["find"].get()
                r.new = self.widgets["replace"].get()
                
            elif isinstance(r, AddStringRule):
                r.text = self.widgets["text"].get()
                r.at_start = (self.pos_var.get() == "start")
                
            elif isinstance(r, ExtensionRule):
                r.mode = self.widgets["mode"].get()
                r.new_ext = self.widgets["ext"].get()
                
            elif isinstance(r, SequenceRule):
                try:
                    r.start = int(self.widgets["start"].get())
                    r.step = int(self.widgets["step"].get())
                except ValueError:
                    pass # Ignore invalid numbers
                    
            # Trigger parent update
            if self.on_change:
                self.on_change(self, "update") # Send special 'update' action
                
        except Exception:
            pass # Prevent crash during typing

class FileToolsDialog(ctk.CTkToplevel):
    """File rename and tools dialog."""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.title("📁 File Tools Pro - Rename & Manage")
        self.geometry("1100x700")
        self.minsize(900, 600)
        
        # Engine
        self.engine = FileToolsEngine()
        self.dup_finder = DuplicateFinder()
        self.cleaner = EmptyFolderCleaner()
        self.attrib_mgr = AttributeManager()
        
        self.files: List[str] = []
        self.rule_widgets: List[RuleWidget] = []
        
        # UI State
        self.current_mode = "rename" # rename, duplicates, cleanup, attributes
        self._monitoring = False
        self._monitor_thread = None
        
        self._create_ui()
        
        # Start monitor
        self._start_monitor()

    def destroy(self):
        self._monitoring = False
        super().destroy()
        
    def _create_ui(self):
        self.grid_columnconfigure(1, weight=1) 
        self.grid_rowconfigure(0, weight=1)
        
        # === LEFT PANEL: CONTROLS ===
        self.left_panel = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.left_panel.grid(row=0, column=0, sticky="nsew")
        self.left_panel.grid_propagate(False)
        self.left_panel.grid_rowconfigure(3, weight=1)
        
        # Mode Switcher
        mode_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        mode_frame.pack(fill="x", padx=10, pady=10)
        
        self.mode_var = ctk.StringVar(value="rename")
        ctk.CTkSegmentedButton(
            mode_frame,
            values=["Rename", "Duplicates", "Cleanup", "Attribs"],
            variable=self.mode_var,
            command=self._switch_mode
        ).pack(fill="x")

        # --- RENAME MODE CONTENT ---
        self.rename_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        self.rename_frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            self.rename_frame, text="Quy tắc (Rule Stack)", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=5)
        
        # Add Rule Buttons (Rename)
        rule_btn_frame = ctk.CTkFrame(self.rename_frame, fg_color="transparent")
        rule_btn_frame.pack(fill="x", padx=10)
        
        for i, (text, cmd) in enumerate([
            ("ABC (Case)", lambda: self._add_rule(CaseRule("lower"))),
            ("Replace", lambda: self._add_rule(ReplaceRule("", ""))),
            ("Trim", lambda: self._add_rule(TrimRule())),
            ("VN Accents", lambda: self._add_rule(RemoveAccentsRule())),
            ("Add Text", lambda: self._add_rule(AddStringRule("New"))),
            ("Numbering", lambda: self._add_rule(SequenceRule())),
            ("Extension", lambda: self._add_rule(ExtensionRule())),
        ]):
            btn = ctk.CTkButton(
                rule_btn_frame, text=text, height=24, font=ctk.CTkFont(size=11), command=cmd
            )
            btn.grid(row=i//2, column=i%2, padx=2, pady=2, sticky="ew")
            
        rule_btn_frame.grid_columnconfigure(0, weight=1)
        rule_btn_frame.grid_columnconfigure(1, weight=1)

        # Auto Refresh Toggle
        self.var_auto_refresh = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.rename_frame, text="Auto-Refresh Preview", variable=self.var_auto_refresh).pack(pady=5)

        self.rule_stack = ctk.CTkScrollableFrame(self.rename_frame)
        self.rule_stack.pack(fill="both", expand=True, padx=5, pady=10)
        
        # --- DUPLICATE MODE CONTENT ---
        self.dup_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        # Initially hidden
        
        ctk.CTkLabel(
            self.dup_frame, text="Duplicate Finder", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=5)
        
        self.btn_scan = ctk.CTkButton(
            self.dup_frame, text="🔍 SCAN NOW", height=40, font=ctk.CTkFont(weight="bold"),
            command=self._scan_duplicates
        )
        self.btn_scan.pack(fill="x", padx=10, pady=20)
        
        ctk.CTkLabel(self.dup_frame, text="Options:", anchor="w").pack(fill="x", padx=10)
        self.var_dup_hash = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.dup_frame, text="Check Content (Hash)", variable=self.var_dup_hash).pack(anchor="w", padx=20, pady=5)
        
        # Auto Select
        ctk.CTkLabel(self.dup_frame, text="Auto Select:", anchor="w").pack(fill="x", padx=10, pady=(20,5))
        ctk.CTkButton(self.dup_frame, text="Select All Except First", command=lambda: self._dup_select("rest")).pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(self.dup_frame, text="Select Newest", command=lambda: self._dup_select("newest")).pack(fill="x", padx=10, pady=2)
        
        # --- CLEANUP CONTENT ---
        self.cleanup_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        ctk.CTkLabel(self.cleanup_frame, text="Empty Folder Cleaner", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        self.btn_scan_empty = ctk.CTkButton(self.cleanup_frame, text="🗑️ SCAN EMPTY FOLDERS", height=40, font=ctk.CTkFont(weight="bold"), command=self._scan_empty_folders)
        self.btn_scan_empty.pack(fill="x", padx=10, pady=20)
        
        # --- ATTRIBUTES CONTENT ---
        self.attrib_frame = ctk.CTkFrame(self.left_panel, fg_color="transparent")
        ctk.CTkLabel(self.attrib_frame, text="Attribute Changer", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        ctk.CTkLabel(self.attrib_frame, text="Set Flags:", anchor="w").pack(fill="x", padx=10, pady=(10,0))
        self.var_readonly = ctk.BooleanVar()
        self.var_hidden = ctk.BooleanVar()
        ctk.CTkCheckBox(self.attrib_frame, text="Read-only", variable=self.var_readonly).pack(anchor="w", padx=20, pady=5)
        ctk.CTkCheckBox(self.attrib_frame, text="Hidden", variable=self.var_hidden).pack(anchor="w", padx=20, pady=5)
        
        self.btn_apply_attribs = ctk.CTkButton(self.attrib_frame, text="Apply Attributes", command=self._apply_attributes)
        self.btn_apply_attribs.pack(fill="x", padx=10, pady=10)
        
        # === MIDDLE PANEL ===
        mid_panel = ctk.CTkFrame(self, corner_radius=0)
        mid_panel.grid(row=0, column=1, sticky="nsew", padx=2)
        mid_panel.grid_rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ctk.CTkFrame(mid_panel, height=40)
        toolbar.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(toolbar, text="➕ Thêm Files", command=self._add_files).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="📁 Thêm Folder", command=self._add_folder).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="🗑️ Xóa hết", fg_color="#DC2626", command=self._clear_files).pack(side="right", padx=5)
        
        # -- Rename Preview (Treeview) --
        self.preview_frame = ctk.CTkFrame(mid_panel, fg_color="transparent")
        self.preview_frame.pack(fill="both", expand=True) # Default visible
        
        columns = ("original", "arrow", "new", "status")
        self.tree = ttk.Treeview(self.preview_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("original", text="Tên gốc")
        self.tree.heading("arrow", text="", anchor="center")
        self.tree.heading("new", text="Tên mới")
        self.tree.heading("status", text="Trạng thái")
        self.tree.column("original", width=300)
        self.tree.column("arrow", width=30, anchor="center")
        self.tree.column("new", width=300)
        self.tree.column("status", width=100)
        
        vsb = ttk.Scrollbar(self.preview_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")
        
        self.tree.tag_configure("ok", foreground="green")
        self.tree.tag_configure("conflict", foreground="red")
        self.tree.tag_configure("unchanged", foreground="gray")
        
        # -- Duplicate Results (Scrollable) --
        self.dup_results_frame = ctk.CTkScrollableFrame(mid_panel, label_text="Duplicate Groups")
        # Hidden by default
        
        # -- Cleanup Results (Listbox) --
        self.cleanup_results_frame = ctk.CTkFrame(mid_panel, fg_color="transparent")
        self.list_empty_folders = tk.Listbox(self.cleanup_results_frame, bg="#1F2937", fg="white", borderwidth=0, highlightthickness=0)
        self.list_empty_folders.pack(fill="both", expand=True, padx=5, pady=5)

        # === RIGHT PANEL ===
        self.right_panel = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.right_panel.grid(row=0, column=2, sticky="nsew")
        self.right_panel.grid_propagate(False)
        
        ctk.CTkLabel(self.right_panel, text="Hành động", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Rename Actions
        self.rename_actions = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        self.rename_actions.pack(fill="both", expand=True)
        
        self.btn_process = ctk.CTkButton(
            self.rename_actions, text="🚀 RENAME", height=50, fg_color="#22C55E", 
             font=ctk.CTkFont(size=16, weight="bold"), command=self._process
        )
        self.btn_process.pack(fill="x", padx=10, pady=(20, 10))
        
        self.btn_undo = ctk.CTkButton(
            self.rename_actions, text="↺ UNDO", height=40, fg_color="#EF4444", command=self._undo
        )
        self.btn_undo.pack(fill="x", padx=10, pady=5)
        
        self.lbl_summary = ctk.CTkLabel(self.rename_actions, text="0 files selected")
        self.lbl_summary.pack(pady=10)
        
        # Duplicate Actions
        self.dup_actions = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        
        ctk.CTkButton(
            self.dup_actions, text="DELETE CHECKED", height=50, fg_color="#DC2626", hover_color="#B91C1C",
            font=ctk.CTkFont(size=14, weight="bold"), command=self._delete_duplicates
        ).pack(fill="x", padx=10, pady=20)
        
        # Cleanup Actions
        self.cleanup_actions = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        ctk.CTkButton(
            self.cleanup_actions, text="DELETE EMPTY", height=50, fg_color="#DC2626", hover_color="#B91C1C",
            font=ctk.CTkFont(size=14, weight="bold"), command=self._delete_empty_folders
        ).pack(fill="x", padx=10, pady=20)
        
        # Attrib Actions
        self.attrib_actions = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        
        self.center_window()

    def center_window(self):
        self.update_idletasks()
        try:
            x = (self.winfo_screenwidth() - 1100) // 2
            y = (self.winfo_screenheight() - 700) // 2
            self.geometry(f"+{x}+{y}")
        except: pass

    def _switch_mode(self, mode):
        self.current_mode = mode.lower()
        
        # Hide all
        self.rename_frame.pack_forget()
        self.dup_frame.pack_forget()
        self.cleanup_frame.pack_forget()
        self.attrib_frame.pack_forget()
        
        self.preview_frame.pack_forget()
        self.dup_results_frame.pack_forget()
        self.cleanup_results_frame.pack_forget()
        
        self.rename_actions.pack_forget()
        self.dup_actions.pack_forget()
        self.cleanup_actions.pack_forget()
        self.attrib_actions.pack_forget()
        
        # Show specific
        if self.current_mode == "rename":
            self.rename_frame.pack(fill="both", expand=True)
            self.preview_frame.pack(fill="both", expand=True)
            self.rename_actions.pack(fill="both", expand=True)
            
        elif self.current_mode == "duplicates":
            self.dup_frame.pack(fill="both", expand=True)
            self.dup_results_frame.pack(fill="both", expand=True)
            self.dup_actions.pack(fill="both", expand=True)
            
        elif self.current_mode == "cleanup":
            self.cleanup_frame.pack(fill="both", expand=True)
            self.cleanup_results_frame.pack(fill="both", expand=True)
            self.cleanup_actions.pack(fill="both", expand=True)
            
        elif self.current_mode == "attribs":
            self.attrib_frame.pack(fill="both", expand=True)
            self.preview_frame.pack(fill="both", expand=True) # Use same file list
            self.attrib_actions.pack(fill="both", expand=True)
    
    # --- CLEANUP LOGIC ---
    def _scan_empty_folders(self):
        # We need a root folder to scan
        folder = filedialog.askdirectory(title="Chọn Folder để quét Rác")
        if not folder: return
        
        self.empty_folders = self.cleaner.find_empty_folders([folder])
        self.list_empty_folders.delete(0, tk.END)
        for f in self.empty_folders:
            self.list_empty_folders.insert(tk.END, f)
            
        messagebox.showinfo("Scan", f"Tìm thấy {len(self.empty_folders)} folder rỗng.")
        
    def _delete_empty_folders(self):
        if not hasattr(self, 'empty_folders') or not self.empty_folders:
            return
            
        if not messagebox.askyesno("Delete", f"Xóa {len(self.empty_folders)} folder rỗng?"):
            return
            
        results = self.cleaner.delete_folders(self.empty_folders)
        success = sum(1 for _, ok, _ in results if ok)
        messagebox.showinfo("Done", f"Đã xóa {success} folder.")
        
        self.list_empty_folders.delete(0, tk.END)
        self.empty_folders = []
        
    # --- ATTRIB LOGIC ---
    def _apply_attributes(self):
        if not self.files:
            messagebox.showinfo("Info", "Chưa có file nào được chọn.")
            return
            
        ro = self.var_readonly.get()
        hid = self.var_hidden.get()
        
        count = 0
        for f in self.files:
            ok, msg = self.attrib_mgr.set_attributes(f, readonly=ro, hidden=hid)
            if ok: count += 1
            
        messagebox.showinfo("Done", f"Đã áp dụng thuộc tính cho {count} file.")

    def _scan_duplicates(self):
        if not self.files:
            messagebox.showinfo("Info", "Chọn File hoặc Folder trước.")
            return
            
        # Run in thread
        self.btn_scan.configure(state="disabled", text="Scanning...")
        threading.Thread(target=self._run_scan_thread, daemon=True).start()
        
    def _run_scan_thread(self):
        try:
            results = self.dup_finder.find_duplicates(self.files)
            self.after(0, lambda: self._show_dup_results(results))
        except Exception:
             self.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
             self.after(0, lambda: self.btn_scan.configure(state="normal", text="🔍 SCAN NOW"))
             
    def _show_dup_results(self, groups: List[DuplicateGroup]):
        for w in self.dup_results_frame.winfo_children():
            w.destroy()
            
        self.dup_widgets = []
        
        if not groups:
            ctk.CTkLabel(self.dup_results_frame, text="Không tìm thấy file trùng!").pack(pady=20)
            return
            
        for g in groups:
            w = DuplicateResultWidget(self.dup_results_frame, g, self._open_file)
            w.pack(fill="x", pady=5)
            self.dup_widgets.append(w)
            
    def _dup_select(self, strategy: str):
        """Auto select duplicates."""
        for w in self.dup_widgets:
            files = w.group.files
            vars = w.vars
            
            # Reset
            for v, _ in vars: v.set(False)
            
            if strategy == "rest":
                # Select all except first
                for i in range(1, len(vars)):
                    vars[i][0].set(True)
            elif strategy == "newest":
                # Find newest file time
                try:
                    times = [os.path.getmtime(f) for f in files]
                    newest_idx = times.index(max(times))
                    # Select ONLY newest? Usually we want to KEEP newest, so select others?
                    # Let's assume user wants to DELETE selected. So keep newest -> Select others.
                    for i in range(len(vars)):
                        if i != newest_idx:
                            vars[i][0].set(True)
                except: pass

    def _delete_duplicates(self):
        to_delete = []
        for w in self.dup_widgets:
            for v, path in w.vars:
                if v.get():
                    to_delete.append(path)
                    
        if not to_delete:
            return
            
        if not messagebox.askyesno("Delete", f"Xóa {len(to_delete)} file đã chọn?\n(Lưu ý: Không thể hoàn tác từ đây)"):
            return
            
        count = 0
        for f in to_delete:
            try:
                os.remove(f) # TODO: Send to trash
                count += 1
            except Exception as e:
                print(e)
                
        messagebox.showinfo("Done", f"Đã xóa {count} file.")
        self._scan_duplicates() # Refresh

    def _open_file(self, path):
         os.startfile(path)
         
    # ... Existing methods (_process, _undo, etc) preserved but indented if needed ...
        
    def _add_rule(self, rule: RenameRule):
        """Add a rule to the stack."""
        self.engine.add_rule(rule)
        
        # Add widget
        widget = RuleWidget(
            self.rule_stack, 
            rule, 
            on_remove=None, # Deprecated
            on_change=self._handle_rule_action
        )
        widget.pack(fill="x", pady=2)
        self.rule_widgets.append(widget)
        
        self._refresh_preview()
        
    def _handle_rule_action(self, widget: RuleWidget, action: str):
        """Handle actions from RuleWidget (up, down, remove)."""
        idx = self.rule_widgets.index(widget)
        
        if action == "remove":
            self.engine.rules.pop(idx)
            self.rule_widgets.pop(idx)
            widget.destroy()
            
        elif action == "up":
            if idx > 0:
                # Swap in core
                self.engine.rules[idx], self.engine.rules[idx-1] = self.engine.rules[idx-1], self.engine.rules[idx]
                # Swap in UI list
                self.rule_widgets[idx], self.rule_widgets[idx-1] = self.rule_widgets[idx-1], self.rule_widgets[idx]
                # Repack All (Simplest way to reorder)
                for w in self.rule_widgets:
                    w.pack_forget()
                    w.pack(fill="x", pady=2)
                    
        elif action == "down":
            if idx < len(self.rule_widgets) - 1:
                # Swap in core
                self.engine.rules[idx], self.engine.rules[idx+1] = self.engine.rules[idx+1], self.engine.rules[idx]
                # Swap in UI list
                self.rule_widgets[idx], self.rule_widgets[idx+1] = self.rule_widgets[idx+1], self.rule_widgets[idx]
                # Repack All
                for w in self.rule_widgets:
                    w.pack_forget()
                    w.pack(fill="x", pady=2)
                    
        self._refresh_preview()

    def _undo(self):
        """Undo last rename."""
        if not messagebox.askyesno("Undo", "Bạn có chắc chắn muốn hoàn tác lần đổi tên gần nhất?"):
            return
            
        results = self.engine.undo_last_transaction()
        if not results:
            messagebox.showinfo("Undo", "Không có lịch sử để hoàn tác.")
            return
            
        success_count = sum(1 for _, ok, _ in results if ok)
        messagebox.showinfo("Undo", f"Đã hoàn tác {len(results)} files.\nThành công: {success_count}")
        self._refresh_preview()
            
    def _refresh_preview(self):
        """Update preview table."""
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        previews = self.engine.preview(self.files)
        
        for p in previews:
            tag = p.status
            self.tree.insert("", "end", values=(
                os.path.basename(p.original_path),
                "➞",
                p.new_filename,
                p.status
            ), tags=(tag,))
            
        self.lbl_summary.configure(text=f"{len(self.files)} files")
        
    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Chọn files")
        if paths:
            for p in paths:
                if p not in self.files:
                    self.files.append(p)
            self._refresh_preview()
            
    def _add_folder(self):
        folder = filedialog.askdirectory(title="Chọn folder")
        if folder:
            for root, dirs, files in os.walk(folder):
                for f in files:
                    full_path = os.path.join(root, f)
                    if full_path not in self.files:
                        self.files.append(full_path)
            self._refresh_preview()
            
    def _clear_files(self):
        self.files = []
        self._refresh_preview()
        
    def _process(self):
        if not self.files:
            return
            
        if not messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn đổi tên các file này?"):
            return
            
        # Execute
        results = self.engine.execute(self.files)
        
        # Show results (simple log for now)
        success_count = sum(1 for _, ok, _ in results if ok)
        messagebox.showinfo("Hoàn tất", f"Đã xử lý {len(results)} files.\nThành công: {success_count}\nLỗi: {len(results) - success_count}")
        
        # Clear and refresh (files are renamed, so we need to update list or clear)
        # For now, clear to avoid confusion
        self.files = []
        self._refresh_preview()

    # --- MONITORING ---
    def _start_monitor(self):
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        
    def _monitor_loop(self):
        """Poll for file changes."""
        last_state = {}
        
        while self._monitoring:
            if not getattr(self, 'var_auto_refresh', None) or not self.var_auto_refresh.get() or not self.files:
                time.sleep(2)
                continue
                
            changed = False
            current_state = {}
            
            # Check files
            for f in self.files:
                try:
                    if not os.path.exists(f):
                        # File deleted?
                        if f in last_state: changed = True
                        continue
                        
                    mtime = os.path.getmtime(f)
                    current_state[f] = mtime
                    
                    if f not in last_state or last_state[f] != mtime:
                        changed = True
                except: pass
            
            # Check length diff (deleted files)
            if len(current_state) != len(last_state):
                changed = True
                
            if changed:
                # Update UI
                self.after(0, self._refresh_preview)
                last_state = current_state
                
            time.sleep(2)
