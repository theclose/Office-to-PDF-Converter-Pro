"""
FileListPanel — Extracted from main_window_pro.py (R1 refactoring).
Enhanced file list with drag & drop, selection and type indicators.
"""

import os
from pathlib import Path
from typing import List, Optional, Callable

import customtkinter as ctk
from office_converter.utils.localization import get_text
from office_converter.utils.logging_setup import get_logger
from office_converter.utils.dnd_helpers import parse_dropped_paths
from office_converter.core.engine import (
    FileType, ALL_EXTENSIONS, FILE_TYPE_COLORS, ConversionFile
)

logger = get_logger("FileListPanel")


class FileListPanel(ctk.CTkFrame):
    """Enhanced file list with drag & drop, selection and type indicators."""

    def __init__(self, parent, on_selection_change: Optional[Callable] = None, 
                 app_instance=None, **kwargs):
        super().__init__(parent, **kwargs)

        self.files: List[ConversionFile] = []
        self.selected_indices: set = set()  # Track selected file indices
        self.anchor_index: int = -1  # For shift-selection
        self.on_selection_change = on_selection_change
        self.app_instance = app_instance  # Store reference to main app for logging

        self._create_widgets()
        self._setup_drag_drop()
        self._setup_keyboard_bindings()

    def _create_widgets(self):
        """Create file list widgets."""
        # Type indicator bar
        self.type_bar = ctk.CTkFrame(self, height=6, corner_radius=3)
        self.type_bar.pack(fill="x", padx=10, pady=(10, 5))

        self.excel_bar = ctk.CTkFrame(self.type_bar, fg_color=FILE_TYPE_COLORS[FileType.EXCEL])
        self.word_bar = ctk.CTkFrame(self.type_bar, fg_color=FILE_TYPE_COLORS[FileType.WORD])
        self.ppt_bar = ctk.CTkFrame(self.type_bar, fg_color=FILE_TYPE_COLORS[FileType.POWERPOINT])

        # Drop zone / File list
        self.drop_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.drop_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.drop_label = ctk.CTkLabel(
            self.drop_frame,
            text=get_text('drop_zone_hint'),
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self.drop_label.pack(expand=True, pady=30)

        # R1: CTkTextbox replaces tk.Listbox — theme-native, bo góc, smooth scroll
        self.file_listbox = ctk.CTkTextbox(
            self.drop_frame,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            corner_radius=8,
            state="disabled",  # Read-only by default
            wrap="none",
            activate_scrollbars=True
        )
        # Track selection state for compatibility
        self._selected_lines: set = set()
        self._is_ctk_textbox = True  # Flag for compatibility methods

        # Stats row
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=5)

        self.count_label = ctk.CTkLabel(
            stats_frame,
            text="0 files",
            font=ctk.CTkFont(weight="bold")
        )
        self.count_label.pack(side="left")

        self.types_label = ctk.CTkLabel(
            stats_frame,
            text="",
            text_color="gray"
        )
        self.types_label.pack(side="left", padx=10)

    def _setup_drag_drop(self):
        """Setup drag and drop support."""
        try:
            from tkinterdnd2 import DND_FILES

            # Check if root supports DnD
            root = self.winfo_toplevel()
            if hasattr(root, 'drop_target_register'):
                self.drop_frame.drop_target_register(DND_FILES)
                self.drop_frame.dnd_bind('<<Drop>>', self._on_drop)
                self.drop_label.configure(text=get_text('dnd_enabled'))
        except ImportError:
            logger.info("TkinterDnD2 not available, drag & drop disabled")
        except Exception as e:
            logger.warning(f"Could not setup drag & drop: {e}")

    def _setup_keyboard_bindings(self):
        """Setup keyboard shortcuts for file selection."""
        # Ctrl+A to select all
        self.file_listbox.bind('<Control-a>', self._select_all)
        self.file_listbox.bind('<Control-A>', self._select_all)
        
        # Delete to remove selected
        self.file_listbox.bind('<Delete>', self._delete_selected)
        self.file_listbox.bind('<BackSpace>', self._delete_selected)
        
        # Click to select line
        self.file_listbox.bind('<Button-1>', self._on_click_select)

    def _select_all(self, event=None):
        """Select all files."""
        try:
            if self.files:
                self.selected_indices = set(range(len(self.files)))
                self._highlight_selected()
        except Exception as e:
            logger.error(f"Select all error: {e}")
        return "break"

    def _on_click_select(self, event=None):
        """Handle click to select a line in CTkTextbox."""
        try:
            if not self.files:
                return
            # Get clicked line number
            index = self.file_listbox.index(f"@{event.x},{event.y}")
            line_num = int(index.split('.')[0]) - 1  # 0-indexed
            if 0 <= line_num < len(self.files):
                # Toggle selection
                if line_num in self.selected_indices:
                    self.selected_indices.discard(line_num)
                else:
                    self.selected_indices.add(line_num)
                self._highlight_selected()
        except Exception:
            pass

    def _highlight_selected(self):
        """Highlight selected lines in CTkTextbox."""
        try:
            self.file_listbox.configure(state="normal")
            self.file_listbox.tag_remove("selected", "1.0", "end")
            self.file_listbox.tag_config(
                "selected",
                background="#1f6aa5",
                foreground="white"
            )
            for idx in self.selected_indices:
                line = idx + 1
                self.file_listbox.tag_add("selected", f"{line}.0", f"{line}.end")
            self.file_listbox.configure(state="disabled")
        except Exception:
            pass

    def _delete_selected(self, event=None):
        """Delete selected files from list."""
        try:
            if not self.selected_indices:
                return "break"
            # Remove in reverse order to maintain indices
            for idx in sorted(self.selected_indices, reverse=True):
                if 0 <= idx < len(self.files):
                    del self.files[idx]
            self.selected_indices.clear()
            self._refresh_display()
        except Exception as e:
            logger.error(f"Delete selected error: {e}")
        return "break"

    def get_selected_files(self) -> List[ConversionFile]:
        """Get currently selected files (or all if none selected)."""
        if self.selected_indices:
            return [self.files[i] for i in sorted(self.selected_indices) if i < len(self.files)]
        return self.files  # Return all if none selected


    def _on_drop(self, event):
        """Handle dropped files using production-grade Unicode parser."""
        try:
            # Use parse_dropped_paths for robust multi-file Unicode support
            file_paths = parse_dropped_paths(self, event.data)
            added = self.add_files(file_paths)
            
            # Success log message
            if added > 0:
                logger.info(f"Drag & drop: Added {added} file(s)")
                # Log to UI using app instance
                if self.app_instance and hasattr(self.app_instance, '_log'):
                    self.app_instance._log(get_text('files_added_ok').format(added))
        except Exception as e:
            logger.error(f"Drop error: {e}")

    def add_files(self, paths: List[str]) -> int:
        """Add files to the list with success logging."""
        added = 0
        skipped = 0
        try:
            for path in paths:
                # Check extension
                ext = Path(path).suffix.lower()
                if ext not in ALL_EXTENSIONS:
                    skipped += 1
                    continue

                # Check if already exists
                if any(f.path == path for f in self.files):
                    skipped += 1
                    continue

                self.files.append(ConversionFile(path=path))
                added += 1

            if added > 0:
                self._refresh_display()
                # Log success to console
                logger.info(f"Added {added} file(s) successfully" + 
                          (f" (skipped {skipped})" if skipped > 0 else ""))
                
        except Exception as e:
            logger.error(f"Add files error: {e}")

        return added

    def clear(self):
        """Clear all files."""
        try:
            self.files.clear()
            self._refresh_display()
        except Exception as e:
            logger.error(f"Clear error: {e}")

    def remove_completed(self):
        """Remove completed files."""
        try:
            self.files = [f for f in self.files if f.status != "completed"]
            self._refresh_display()
        except Exception as e:
            logger.error(f"Remove completed error: {e}")

    def _refresh_display(self):
        """Refresh the file list display with debouncing for large lists."""
        try:
            # Debounce: cancel previous scheduled refresh
            if hasattr(self, '_refresh_job') and self._refresh_job:
                self.after_cancel(self._refresh_job)
            
            # Schedule refresh after 50ms debounce
            self._refresh_job = self.after(50, self._do_refresh_display)
        except Exception as e:
            logger.error(f"Refresh display error: {e}")

    def _do_refresh_display(self):
        """Actual refresh implementation."""
        try:
            count = len(self.files)

            # Update type bar
            self._update_type_bar()

            # Update count
            self.count_label.configure(text=f"{count} file{'s' if count != 1 else ''}")

            # Update type breakdown
            type_counts = {ft: 0 for ft in FileType}
            for f in self.files:
                type_counts[f.file_type] += 1

            parts = []
            if type_counts[FileType.EXCEL]: parts.append(f"📗{type_counts[FileType.EXCEL]}")
            if type_counts[FileType.WORD]: parts.append(f"📘{type_counts[FileType.WORD]}")
            if type_counts[FileType.POWERPOINT]: parts.append(f"📙{type_counts[FileType.POWERPOINT]}")
            self.types_label.configure(text=" ".join(parts))

            # Update list display (R1: CTkTextbox-compatible)
            if count == 0:
                self.file_listbox.pack_forget()
                self.drop_label.pack(expand=True, pady=30)
            else:
                self.drop_label.pack_forget()
                self.file_listbox.pack(fill="both", expand=True)

                # Clear and repopulate CTkTextbox
                self.file_listbox.configure(state="normal")
                self.file_listbox.delete("1.0", "end")

                # Progressive rendering: show only first 200 files for performance
                MAX_DISPLAY = 200
                display_files = self.files[:MAX_DISPLAY]
                
                lines = []
                for i, f in enumerate(display_files, 1):
                    status_icon = {
                        "pending": f.icon,
                        "converting": "⏳",
                        "completed": "✅",
                        "failed": "❌"
                    }.get(f.status, f.icon)
                    # F6: Show file size next to filename
                    try:
                        size_bytes = os.path.getsize(f.path)
                        if size_bytes < 1024:
                            size_str = f"{size_bytes}B"
                        elif size_bytes < 1024 * 1024:
                            size_str = f"{size_bytes / 1024:.0f}KB"
                        else:
                            size_str = f"{size_bytes / (1024 * 1024):.1f}MB"
                    except OSError:
                        size_str = "?"
                    lines.append(f"{status_icon} {i:3d}. {f.filename}  ({size_str})")
                
                # Add "more files" indicator if truncated
                if count > MAX_DISPLAY:
                    lines.append(get_text('more_files_indicator').format(count - MAX_DISPLAY))
                
                self.file_listbox.insert("1.0", "\n".join(lines))
                self.file_listbox.configure(state="disabled")
                
                # Re-apply selection highlighting
                self._highlight_selected()

            # Callback
            if self.on_selection_change:
                self.on_selection_change(self.files)
        except Exception as e:
            logger.error(f"Refresh display error: {e}")

    def _update_type_bar(self):
        """Update the file type distribution bar."""
        try:
            if not self.files:
                self.excel_bar.place_forget()
                self.word_bar.place_forget()
                self.ppt_bar.place_forget()
                return

            type_counts = {ft: 0 for ft in FileType}
            for f in self.files:
                type_counts[f.file_type] += 1

            total = len(self.files)
            x = 0

            for ftype, bar in [(FileType.EXCEL, self.excel_bar),
                               (FileType.WORD, self.word_bar),
                               (FileType.POWERPOINT, self.ppt_bar)]:
                if type_counts[ftype]:
                    width = type_counts[ftype] / total
                    bar.place(relx=x, rely=0, relwidth=width, relheight=1)
                    x += width
                else:
                    bar.place_forget()
        except Exception as e:
            logger.error(f"Update type bar error: {e}")
