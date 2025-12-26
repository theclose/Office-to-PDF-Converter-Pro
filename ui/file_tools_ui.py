"""
UI for File Tools (Rename, etc).
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import os
import threading
from typing import List, Optional

from office_converter.core.file_tools import (
    FileToolsEngine, CaseRule, ReplaceRule, RemoveAccentsRule,
    TrimRule, AddStringRule, SequenceRule, ExtensionRule, RenameRule
)
from office_converter.utils.tkdnd_wrapper import TkDnDWrapper

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
        self.files: List[str] = []
        self.rule_widgets: List[RuleWidget] = []
        
        self._create_ui()
        
        # Center on screen
        self.update_idletasks()
        try:
            x = (self.winfo_screenwidth() - 1100) // 2
            y = (self.winfo_screenheight() - 700) // 2
            self.geometry(f"+{x}+{y}")
        except:
            pass
            
    def _create_ui(self):
        self.grid_columnconfigure(1, weight=1) # Middle panel expands
        self.grid_rowconfigure(0, weight=1)
        
        # === LEFT PANEL: RULES ===
        left_panel = ctk.CTkFrame(self, width=300, corner_radius=0)
        left_panel.grid(row=0, column=0, sticky="nsew")
        left_panel.grid_propagate(False)
        left_panel.grid_rowconfigure(2, weight=1)
        
        # Header
        ctk.CTkLabel(
            left_panel,
            text="Quy tắc (Rule Stack)",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        # Add Rule Buttons
        rule_btn_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        rule_btn_frame.pack(fill="x", padx=10)
        
        # Grid layout for small buttons
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
                rule_btn_frame, 
                text=text, 
                height=24,
                font=ctk.CTkFont(size=11),
                command=cmd
            )
            btn.grid(row=i//2, column=i%2, padx=2, pady=2, sticky="ew")
            
        rule_btn_frame.grid_columnconfigure(0, weight=1)
        rule_btn_frame.grid_columnconfigure(1, weight=1)
        
        # Rule Stack (Scrollable)
        self.rule_stack = ctk.CTkScrollableFrame(left_panel)
        self.rule_stack.pack(fill="both", expand=True, padx=5, pady=10)
        
        # === MIDDLE PANEL: PREVIEW ===
        mid_panel = ctk.CTkFrame(self, corner_radius=0)
        mid_panel.grid(row=0, column=1, sticky="nsew", padx=2)
        mid_panel.grid_rowconfigure(1, weight=1)
        
        # Toolbar
        toolbar = ctk.CTkFrame(mid_panel, height=40)
        toolbar.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(
            toolbar, text="➕ Thêm Files", command=self._add_files
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="📁 Thêm Folder", command=self._add_folder
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar, text="🗑️ Xóa hết", fg_color="#DC2626", hover_color="#B91C1C",
            command=self._clear_files
        ).pack(side="right", padx=5)
        
        # Treeview for Preview
        columns = ("original", "arrow", "new", "status")
        self.tree = ttk.Treeview(mid_panel, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("original", text="Tên gốc")
        self.tree.heading("arrow", text="", anchor="center")
        self.tree.heading("new", text="Tên mới")
        self.tree.heading("status", text="Trạng thái")
        
        self.tree.column("original", width=300)
        self.tree.column("arrow", width=30, anchor="center")
        self.tree.column("new", width=300)
        self.tree.column("status", width=100)
        
        # Scrollbars
        vsb = ttk.Scrollbar(mid_panel, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)
        vsb.pack(side="right", fill="y")
        
        # Configure tag colors
        self.tree.tag_configure("ok", foreground="green")
        self.tree.tag_configure("conflict", foreground="red")
        self.tree.tag_configure("unchanged", foreground="gray")
        
        # === RIGHT PANEL: ACTIONS ===
        right_panel = ctk.CTkFrame(self, width=200, corner_radius=0)
        right_panel.grid(row=0, column=2, sticky="nsew")
        right_panel.grid_propagate(False)
        
        ctk.CTkLabel(
            right_panel,
            text="Hành động",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)
        
        self.btn_process = ctk.CTkButton(
            right_panel,
            text="🚀 THỰC HIỆN",
            height=50,
            fg_color="#22C55E",
            hover_color="#16A34A",
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self._process
        )
        self.btn_process.pack(fill="x", padx=10, pady=(20, 10))
        
        # Undo Button
        self.btn_undo = ctk.CTkButton(
            right_panel,
            text="↺ UNDO",
            height=40,
            fg_color="#EF4444",
            hover_color="#DC2626",
            command=self._undo
        )
        self.btn_undo.pack(fill="x", padx=10, pady=5)
        
        # Summary
        self.lbl_summary = ctk.CTkLabel(right_panel, text="0 files selected")
        self.lbl_summary.pack(pady=10)
        
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
