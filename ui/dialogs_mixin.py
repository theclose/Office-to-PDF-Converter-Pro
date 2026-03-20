"""
DialogsMixin — Extracted from ConverterProApp (B8 God Class decomposition).
Handles dialog windows, logging, settings, and application lifecycle.
All methods use `self.*` and resolve via MRO to ConverterProApp's attributes.
"""

import os
import subprocess
from datetime import datetime
from tkinter import messagebox

import customtkinter as ctk

from office_converter.utils.logging_setup import get_logger
from office_converter.utils.com_pool import release_pool

logger = get_logger("DialogsMixin")


class DialogsMixin:
    """Mixin: dialogs, logging, settings, and app lifecycle.
    
    Requires host class to provide:
        self.db, self.config, self.engine, self.is_converting,
        self.log_textbox, self.file_panel,
        self.after(), self.update_idletasks(), self.destroy()
    """

    # =========== UTILITIES ===========

    def _log(self, message: str):
        """Add log message with timestamp."""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            if self.log_textbox:
                self.log_textbox.insert("end", f"[{timestamp}] {message}\n")
                # F6: Cap log at 2000 lines to prevent memory bloat
                try:
                    line_count = int(self.log_textbox.index("end-1c").split(".")[0])
                    if line_count > 2000:
                        self.log_textbox.delete("1.0", f"{line_count - 1500}.0")
                except Exception:
                    pass
                self.log_textbox.see("end")
            logger.info(message)
        except Exception as e:
            logger.error(f"Log error: {e}")

    # =========== DIALOGS ===========

    def _show_stats(self):
        """Show statistics dialog."""
        try:
            stats = self.db.get_stats()

            dialog = ctk.CTkToplevel(self)
            dialog.title("📊 Thống kê")
            dialog.geometry("350x250")
            dialog.transient(self)
            dialog.grab_set()

            text = f"""
📊 THỐNG KÊ TỔNG HỢP

Tổng files: {stats['total']}
Thành công: {stats['success']}
Thất bại: {stats['failed']}
Tỷ lệ: {stats['success_rate']:.1f}%
Thời gian TB: {stats['avg_duration']:.1f}s
            """

            ctk.CTkLabel(dialog, text=text, font=ctk.CTkFont(size=14),
                        justify="left").pack(expand=True, padx=20, pady=20)

            ctk.CTkButton(dialog, text="Đóng", command=dialog.destroy).pack(pady=10)
        except Exception as e:
            logger.error(f"Show stats error: {e}")
            messagebox.showerror("Lỗi", f"Không thể hiển thị thống kê: {e}")

    def _show_settings(self):
        """Show settings dialog."""
        try:
            from office_converter.ui.dialogs import show_settings
            show_settings(self, self.config, "vi", lambda: None)
        except ImportError:
            messagebox.showinfo("Cài đặt", "Mở config.json để chỉnh sửa cài đặt")
        except Exception as e:
            logger.error(f"Show settings error: {e}")
            messagebox.showinfo("Cài đặt", "Mở config.json để chỉnh sửa cài đặt")

    def _show_shortcuts(self):
        """Show keyboard shortcuts."""
        try:
            shortcuts = """
⌨️ KEYBOARD SHORTCUTS

Ctrl+O     Thêm files
Ctrl+V     Paste files
Delete     Xóa danh sách
Enter      Bắt đầu chuyển đổi
Escape     Dừng chuyển đổi
F1         Xem shortcuts
            """
            messagebox.showinfo("Phím tắt", shortcuts)
        except Exception as e:
            logger.error(f"Show shortcuts error: {e}")

    def _show_recent(self):
        """Show recent files dialog."""
        try:
            from pathlib import Path

            recent = self.db.get_recent(10)

            if not recent:
                messagebox.showinfo("Recent Files", "Chưa có files gần đây")
                return

            dialog = ctk.CTkToplevel(self)
            dialog.title("🕐 Recent Files")
            dialog.geometry("500x400")
            dialog.transient(self)
            dialog.grab_set()

            ctk.CTkLabel(dialog, text="📋 Files gần đây",
                        font=ctk.CTkFont(size=16, weight="bold")).pack(pady=15)

            listbox_frame = ctk.CTkFrame(dialog)
            listbox_frame.pack(fill="both", expand=True, padx=20, pady=10)

            textbox = ctk.CTkTextbox(listbox_frame, font=ctk.CTkFont(size=12))
            textbox.pack(fill="both", expand=True)

            for i, path in enumerate(recent, 1):
                textbox.insert("end", f"{i}. {Path(path).name}\n")
            textbox.configure(state="disabled")

            def add_all():
                if self.file_panel:
                    self.file_panel.add_files(recent)
                dialog.destroy()
                self._log(f"➕ Đã thêm {len(recent)} file(s) từ recent")

            ctk.CTkButton(dialog, text="➕ Thêm tất cả",
                         command=add_all).pack(pady=15)
        except Exception as e:
            logger.error(f"Show recent error: {e}")
            messagebox.showerror("Lỗi", f"Không thể hiển thị recent files: {e}")

    # =========== WINDOW LIFECYCLE ===========

    def _on_window_restore(self, event=None):
        """Handle window restore after minimize - simple refresh."""
        if hasattr(self, '_restore_scheduled') and self._restore_scheduled:
            return
        self._restore_scheduled = True

        def do_restore():
            try:
                self._restore_scheduled = False
                self.update_idletasks()
            except Exception:
                pass

        self.after(100, do_restore)

    def _open_file_tools(self):
        """Open File Tools dialog."""
        try:
            if hasattr(self, 'file_tools_dialog') and self.file_tools_dialog and self.file_tools_dialog.winfo_exists():
                self.file_tools_dialog.lift()
                self.file_tools_dialog.focus_force()
                return

            from office_converter.ui.file_tools_ui_v2 import FileToolsDialog
            self.file_tools_dialog = FileToolsDialog(self)
            self.file_tools_dialog.grab_set()
        except Exception as e:
            logger.error(f"Error opening File Tools: {e}")
            messagebox.showerror("Error", f"Failed to open File Tools: {e}")

    def _on_closing(self):
        """Cleanup on close with forced termination."""
        try:
            import time as _time
            logger.info("Application closing - starting cleanup")

            # 1. Stop conversion engine if running
            if self.engine and self.is_converting:
                logger.info("Stopping conversion engine...")
                self.engine.stop(force=True)
                _time.sleep(0.5)

            # 2. F3: Null COM refs instead of release_pool() (STA violation)
            # COM objects were created on worker thread — don't call Quit() from main.
            try:
                from office_converter.utils.com_pool import get_pool
                pool = get_pool()
                pool._excel = None
                pool._word = None
                pool._ppt = None
                if pool._idle_timer:
                    pool._idle_timer.cancel()
                logger.info("COM pool references cleared")
            except Exception as e:
                logger.debug(f"COM pool clear error: {e}")

            # 3. Close database connection
            try:
                if hasattr(self, 'db') and self.db:
                    # F7: Flush pending batch writes before exit
                    if hasattr(self.db, 'flush'):
                        self.db.flush()
                    if hasattr(self.db, '_conn') and self.db._conn:
                        self.db._conn.close()
                    logger.info("Database flushed and closed")
            except Exception as e:
                logger.debug(f"DB close error: {e}")

            # 4. F4: Parallel taskkill (B7 pattern) — 5s instead of 15s
            try:
                from concurrent.futures import ThreadPoolExecutor

                def _kill(proc_name):
                    subprocess.run(
                        ['taskkill', '/F', '/IM', proc_name],
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        timeout=5
                    )

                with ThreadPoolExecutor(max_workers=3) as pool:
                    futs = [pool.submit(_kill, p) for p in
                            ['EXCEL.EXE', 'WINWORD.EXE', 'POWERPNT.EXE']]
                    for f in futs:
                        try:
                            f.result(timeout=6)
                        except Exception:
                            pass
            except Exception:
                pass

            logger.info("Cleanup complete - forcing exit")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        finally:
            os._exit(0)
