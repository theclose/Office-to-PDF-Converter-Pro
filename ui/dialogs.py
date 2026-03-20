"""
Settings Dialog - Popup for application settings.
"""

import os
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

import sys
ui_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(ui_dir)
root_dir = os.path.dirname(package_dir)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from office_converter.utils.config import Config
from office_converter.utils.localization import get_text, AVAILABLE_LANGUAGES


class SettingsDialog:
    """Settings popup dialog."""

    def __init__(self, parent: tk.Tk, config: Config, lang: str,
                 on_save: Optional[Callable] = None):
        self.parent = parent
        self.config = config
        self.lang = lang
        self.on_save = on_save

        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("⚙️ " + get_text("options_title", lang))
        self.dialog.geometry("450x400")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 450) // 2
        y = (self.dialog.winfo_screenheight() - 400) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Variables
        self.var_language = tk.StringVar(value=config.language)
        self.var_theme = tk.StringVar(value=config.theme)
        self.var_quality = tk.IntVar(value=config.pdf_quality)
        self.var_auto_open = tk.BooleanVar(value=config.get("auto_open_folder", True))
        self.var_recycle_threshold = tk.IntVar(value=config.get("recycle_threshold", 50))
        self.var_default_author = tk.StringVar(value=config.get("default_author", ""))

        self._create_widgets()

    def _create_widgets(self):
        """Create dialog widgets."""
        notebook = ttk.Notebook(self.dialog)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # === Tab 1: General ===
        tab_general = ttk.Frame(notebook, padding=10)
        notebook.add(tab_general, text="🔧 General")

        # Language
        frame_lang = ttk.LabelFrame(tab_general, text="🌐 Language", padding=5)
        frame_lang.pack(fill="x", pady=5)

        for code, name in AVAILABLE_LANGUAGES.items():
            ttk.Radiobutton(frame_lang, text=name,
                           variable=self.var_language, value=code).pack(anchor="w")

        # Theme
        frame_theme = ttk.LabelFrame(tab_general, text="🎨 Theme", padding=5)
        frame_theme.pack(fill="x", pady=5)

        ttk.Radiobutton(frame_theme, text="☀️ Light Mode",
                       variable=self.var_theme, value="light").pack(side="left", padx=10)
        ttk.Radiobutton(frame_theme, text="🌙 Dark Mode",
                       variable=self.var_theme, value="dark").pack(side="left", padx=10)

        # Auto open folder
        ttk.Checkbutton(tab_general, text="📂 Auto open folder after conversion",
                       variable=self.var_auto_open).pack(anchor="w", pady=5)

        # === Tab 2: PDF ===
        tab_pdf = ttk.Frame(notebook, padding=10)
        notebook.add(tab_pdf, text="📄 PDF")

        # Quality
        frame_quality = ttk.LabelFrame(tab_pdf, text="Quality", padding=5)
        frame_quality.pack(fill="x", pady=5)

        ttk.Radiobutton(frame_quality, text="📄 High Quality (Larger files)",
                       variable=self.var_quality, value=0).pack(anchor="w")
        ttk.Radiobutton(frame_quality, text="📦 Minimum Size (Smaller files)",
                       variable=self.var_quality, value=1).pack(anchor="w")

        # Default author
        frame_author = ttk.LabelFrame(tab_pdf, text="Default Metadata", padding=5)
        frame_author.pack(fill="x", pady=5)

        ttk.Label(frame_author, text="Author:").pack(anchor="w")
        ttk.Entry(frame_author, textvariable=self.var_default_author, width=30).pack(anchor="w", pady=2)

        # === Tab 3: Performance ===
        tab_perf = ttk.Frame(notebook, padding=10)
        notebook.add(tab_perf, text="⚡ Performance")

        frame_perf = ttk.LabelFrame(tab_perf, text="COM Pool Settings", padding=5)
        frame_perf.pack(fill="x", pady=5)

        ttk.Label(frame_perf, text="Recycle COM after N conversions:").pack(anchor="w")
        scale = ttk.Scale(frame_perf, from_=10, to=100, variable=self.var_recycle_threshold,
                         orient="horizontal", length=200)
        scale.pack(anchor="w", pady=5)

        self.lbl_threshold = ttk.Label(frame_perf, text=f"Current: {self.var_recycle_threshold.get()}")
        self.lbl_threshold.pack(anchor="w")

        def update_label(val):
            self.lbl_threshold.config(text=f"Current: {int(float(val))}")
        scale.config(command=update_label)

        ttk.Label(tab_perf, text="💡 Higher = faster (less restarts)\n     Lower = less memory usage",
                 foreground="gray").pack(anchor="w", pady=10)

        # === Buttons ===
        frame_btns = ttk.Frame(self.dialog)
        frame_btns.pack(fill="x", padx=10, pady=10)

        ttk.Button(frame_btns, text="💾 Save", command=self._save).pack(side="right", padx=5)
        ttk.Button(frame_btns, text="❌ Cancel", command=self.dialog.destroy).pack(side="right")

    def _save(self):
        """Save settings and close."""
        self.config.language = self.var_language.get()
        self.config.theme = self.var_theme.get()
        self.config.pdf_quality = self.var_quality.get()
        self.config.set("auto_open_folder", self.var_auto_open.get())
        self.config.set("recycle_threshold", int(self.var_recycle_threshold.get()))
        self.config.set("default_author", self.var_default_author.get())
        self.config.save()

        if self.on_save:
            self.on_save()

        self.dialog.destroy()


def show_settings(parent: tk.Tk, config: Config, lang: str,
                  on_save: Optional[Callable] = None):
    """Show settings dialog."""
    SettingsDialog(parent, config, lang, on_save)
