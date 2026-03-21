"""
ConversionMixin — Extracted from ConverterProApp (B8 God Class decomposition).
Handles conversion orchestration, progress UI, and callbacks.
All methods use `self.*` and resolve via MRO to ConverterProApp's attributes.
"""

import os
import time
import threading
from pathlib import Path
from datetime import datetime
from tkinter import messagebox
from office_converter.utils.localization import get_text

from office_converter.utils.logging_setup import get_logger
from office_converter.core.engine import (
    ConversionFile, ConversionOptions, ConversionEngine
)
from office_converter.utils.pdf_tools import parse_page_range

logger = get_logger("ConversionMixin")


class ConversionMixin:
    """Mixin: conversion start/stop/progress/callbacks.
    
    Requires host class to provide:
        self.file_panel, self.engine, self.is_converting,
        self.btn_convert, self.progress_bar, self.progress_percent,
        self.progress_label, self.progress_title, self.status_badge,
        self.elapsed_label, self.remaining_label, self.estimated_label,
        self.current_file_label, self.progress_frame, self.btn_stop,
        self.main_content_frame, self.output_folder, self.log_textbox,
        self.conversion_start_time, self.total_estimated_time,
        self.var_quality, self.var_dpi, self.var_scan_mode,
        self.var_password, self.var_password_enabled,
        self.var_page_range, self.var_sheet_option, self.var_sheet_index,
        self._last_progress_update, self._progress_throttle_ms,
        self._log_buffer, self._log_flush_job, self._anim_target,
        self.after(), self.update_idletasks(), self._log()
    """

    # =========== ERROR PREVENTION (Phase 4) ===========

    def _toggle_inputs(self, is_running: bool) -> None:
        """Phase 4: Disable/enable all inputs during conversion.
        Prevents user from changing settings mid-batch or triggering duplicates.
        
        Args:
            is_running: True = lock inputs, False = unlock inputs
        """
        state = "disabled" if is_running else "normal"
        try:
            # Options panel widgets
            for attr_name in ('dpi_entry', 'password_entry'):
                widget = getattr(self, attr_name, None)
                if widget:
                    widget.configure(state=state)

            # File action buttons (add, clear, output)
            for attr_name in ('btn_add_files', 'btn_clear_files', 'btn_output'):
                widget = getattr(self, attr_name, None)
                if widget:
                    widget.configure(state=state)

            # File listbox (prevent delete/selection during conversion)
            if hasattr(self, 'file_panel') and self.file_panel:
                listbox = getattr(self.file_panel, 'file_listbox', None)
                if listbox:
                    listbox.configure(state=state)

            # Keyboard shortcuts: unbind dangerous ones during conversion
            if is_running:
                self.unbind('<Return>')    # Prevent duplicate start
                self.unbind('<Delete>')    # Prevent clearing file list
                self.unbind('<Control-o>') # Prevent adding files
            else:
                # Re-bind shortcuts
                self.bind('<Return>', lambda e: self._start_conversion())
                self.bind('<Delete>', lambda e: self._clear_files())
                self.bind('<Control-o>', lambda e: self._add_files())

        except Exception as e:
            logger.error(f"Toggle inputs error: {e}")

    # =========== CONVERSION ===========

    def _start_conversion(self):
        """Start conversion process."""
        try:
            if not self.file_panel or not self.file_panel.files or self.is_converting:
                return

            self.is_converting = True
            self.conversion_start_time = time.time()

            # Default estimate (5s per file)
            self.total_estimated_time = len(self.file_panel.files) * 5.0

            # UI updates
            if self.btn_convert:
                self.btn_convert.configure(state="disabled", text=get_text('converting_progress'))

            # Phase 4: Lock all inputs to prevent user error
            self._toggle_inputs(True)

            # Reset progress UI
            if self.progress_bar:
                self.progress_bar.set(0)
            if self.progress_percent:
                self.progress_percent.configure(text="0%", text_color="#22C55E")
            if self.progress_label:
                total = len(self.file_panel.files)
                self.progress_label.configure(text=get_text('progress_files').format(0, total))
            if self.progress_title:
                self.progress_title.configure(text=get_text('progress_converting'))
            if self.status_badge:
                self.status_badge.configure(text=get_text('progress_status'), fg_color="#3B82F6")
            if self.elapsed_label:
                self.elapsed_label.configure(text="00:00")
            if self.remaining_label:
                est_mins, est_secs = divmod(int(self.total_estimated_time), 60)
                self.remaining_label.configure(text=f"{est_mins:02d}:{est_secs:02d}")
            if self.estimated_label:
                est_mins, est_secs = divmod(int(self.total_estimated_time), 60)
                self.estimated_label.configure(text=f"{est_mins:02d}:{est_secs:02d}")
            if self.current_file_label:
                self.current_file_label.configure(text=get_text('waiting'))

            # Show progress frame (below main content area)
            if self.progress_frame:
                self.progress_frame.pack(fill="x", pady=15)

            # P3: Show compact progress + stop button in right panel
            if hasattr(self, 'compact_progress_frame'):
                self.compact_progress_frame.pack(
                    fill="x", padx=10, pady=5,
                    after=self.btn_convert.master  # after convert_section
                )
                self.compact_progress_bar.set(0)
                self.compact_percent.configure(text="0%")
                total = len(self.file_panel.files)
                self.compact_file_count.configure(text=f"0/{total}")
                self.compact_current_file.configure(text=get_text('waiting'))
                self.compact_time.configure(text="\u23f1 00:00  \u23f3 --:--")
            if hasattr(self, 'btn_stop') and self.btn_stop:
                self.btn_stop.pack(fill="x", pady=(5, 0))
            if hasattr(self, 'btn_convert') and self.btn_convert:
                self.btn_convert.pack_forget()

            # Parse DPI
            try:
                dpi = int(self.var_dpi.get())
            except (ValueError, TypeError):
                dpi = 300

            # Create options
            options = ConversionOptions(
                quality=self.var_quality.get(),
                quality_dpi=dpi,
                auto_compress=self.var_auto_compress.get(),
                scan_mode=self.var_scan_mode.get(),
                password=self.var_password.get() if self.var_password_enabled.get() else None,
                page_range=self.var_page_range.get() or None,
            )

            if self.var_sheet_option.get() == 1:
                parsed = parse_page_range(self.var_sheet_index.get())
                if parsed:
                    options.sheet_indices = [i + 1 for i in parsed]

            # Create engine with callbacks
            self.engine = ConversionEngine(
                on_progress=self._on_progress,
                on_file_complete=self._on_file_complete,
                on_error=self._on_error
            )

            # Start time display
            self._update_time_display()

            # Force UI update to prevent freeze before thread starts
            self.update_idletasks()

            # Start conversion thread
            thread = threading.Thread(
                target=self._run_conversion,
                args=(options,),
                daemon=True
            )
            thread.start()
        except Exception as e:
            self.is_converting = False
            logger.error(f"Start conversion error: {e}")
            messagebox.showerror(get_text('error'), get_text('cannot_start').format(e))

    def _calculate_estimated_time(self) -> float:
        """Calculate total estimated conversion time."""
        try:
            from office_converter.utils.progress_estimator import estimate_conversion_time
            total = 0.0
            if self.file_panel:
                for f in self.file_panel.files:
                    try:
                        total += estimate_conversion_time(f.path)
                    except Exception:
                        total += 10.0
            return max(total, 5.0)
        except Exception:
            if self.file_panel:
                return len(self.file_panel.files) * 5.0
            return 10.0

    def _run_conversion(self, options: ConversionOptions):
        """Run conversion in background thread."""
        try:
            if self.engine and self.file_panel:
                self.engine.convert_batch(
                    self.file_panel.files,
                    options,
                    self.output_folder if self.output_folder else None
                )
        except Exception as e:
            logger.error(f"Run conversion error: {e}")
        finally:
            self.after(0, self._on_conversion_done)

    def _stop_conversion(self):
        """Stop conversion immediately (force stop)."""
        try:
            if self.engine:
                self._log(get_text('stopping'))

                # Force stop - kills Office processes if needed
                self.engine.stop(force=True)

                # Immediately update UI
                self.is_converting = False

                # Hide progress frame
                if hasattr(self, 'progress_frame') and self.progress_frame:
                    self.progress_frame.pack_forget()

                # P3: Hide compact progress and stop, restore convert button
                if hasattr(self, 'compact_progress_frame'):
                    self.compact_progress_frame.pack_forget()
                if hasattr(self, 'btn_stop') and self.btn_stop:
                    self.btn_stop.pack_forget()

                # Re-enable convert button and show main content
                if hasattr(self, 'btn_convert') and self.btn_convert:
                    self.btn_convert.pack(fill="x")
                    self.btn_convert.configure(state="normal", text=get_text('btn_convert'))
                if hasattr(self, 'main_content_frame') and self.main_content_frame:
                    self.main_content_frame.pack(fill="both", expand=True, padx=15, pady=10)

                self._log(get_text('stopped'))

                # Phase 4: Unlock inputs
                self._toggle_inputs(False)

                # Mark pending files as cancelled
                if self.file_panel:
                    for f in self.file_panel.files:
                        if f.status == "converting" or f.status == "pending":
                            f.status = "pending"  # Reset to pending
                    self.file_panel._refresh_display()

        except Exception as e:
            logger.error(f"Stop conversion error: {e}")

    # =========== PROGRESS CALLBACKS (B3 throttled) ===========

    def _on_progress(self, current: int, total: int, filename: str):
        """Progress callback from engine.
        B3: Throttled to max 1 update per _progress_throttle_ms (100ms)."""
        try:
            now = time.time()
            elapsed_ms = (now - self._last_progress_update) * 1000

            is_first_or_last = (current == 0 or current + 1 >= total)

            if elapsed_ms >= self._progress_throttle_ms or is_first_or_last:
                self._last_progress_update = now
                progress = (current + 1) / total
                self.after(0, lambda: self._update_progress_ui(progress, current, total, filename))
        except Exception as e:
            logger.error(f"On progress error: {e}")

    def _update_progress_ui(self, progress: float, current: int, total: int, filename: str):
        """Update progress UI on main thread."""
        try:
            percent = int(progress * 100)

            if self.progress_bar:
                self._animate_progress(progress)

            if self.progress_percent:
                if percent < 30:
                    color = "#22C55E"
                elif percent < 70:
                    color = "#3B82F6"
                else:
                    color = "#22C55E"
                self.progress_percent.configure(text=f"{percent}%", text_color=color)

            if self.progress_label:
                self.progress_label.configure(text=get_text('progress_files').format(current + 1, total))

            if self.current_file_label:
                display_name = filename if len(filename) <= 50 else filename[:47] + "..."
                self.current_file_label.configure(text=display_name)

            if self.remaining_label:
                elapsed = time.time() - self.conversion_start_time
                if progress > 0.05:
                    estimated_total = elapsed / progress
                    remaining = max(0, estimated_total - elapsed)
                else:
                    remaining = self.total_estimated_time - elapsed

                rem_mins, rem_secs = divmod(int(max(0, remaining)), 60)
                self.remaining_label.configure(text=f"{rem_mins:02d}:{rem_secs:02d}")

            # P3: Sync compact progress panel
            if hasattr(self, 'compact_progress_bar'):
                self.compact_progress_bar.set(progress)
            if hasattr(self, 'compact_percent'):
                self.compact_percent.configure(text=f"{percent}%")
            if hasattr(self, 'compact_file_count'):
                self.compact_file_count.configure(text=f"{current + 1}/{total}")
            if hasattr(self, 'compact_current_file'):
                display_name = filename if len(filename) <= 35 else filename[:32] + "..."
                self.compact_current_file.configure(text=display_name)
            if hasattr(self, 'compact_time') and hasattr(self, 'conversion_start_time'):
                elapsed = time.time() - self.conversion_start_time
                e_m, e_s = divmod(int(elapsed), 60)
                if progress > 0.05:
                    remaining = max(0, (elapsed / progress) - elapsed)
                else:
                    remaining = self.total_estimated_time - elapsed
                r_m, r_s = divmod(int(max(0, remaining)), 60)
                self.compact_time.configure(
                    text=f"\u23f1 {e_m:02d}:{e_s:02d}  \u23f3 {r_m:02d}:{r_s:02d}"
                )

        except Exception as e:
            logger.error(f"Update progress UI error: {e}")

    def _animate_progress(self, target: float, steps: int = 5):
        """Smoothly animate progress bar to target value.
        B3: Coalesces rapid calls — only the latest target is animated."""
        try:
            current = self.progress_bar.get() if hasattr(self.progress_bar, 'get') else 0

            if target <= current or abs(target - current) < 0.01:
                self.progress_bar.set(target)
                return

            self._anim_target = target

            if hasattr(self, '_anim_running') and self._anim_running:
                return

            step_size = (target - current) / steps
            self._anim_running = True

            def animate_step(step_num, base_current):
                if step_num >= steps:
                    self.progress_bar.set(self._anim_target)
                    self._anim_running = False
                    return

                new_value = base_current + (step_size * (step_num + 1))
                self.progress_bar.set(min(new_value, self._anim_target))

                self.after(16, lambda: animate_step(step_num + 1, base_current))

            animate_step(0, current)
        except Exception:
            self._anim_running = False
            self.progress_bar.set(target)

    def _on_file_complete(self, conv_file: ConversionFile):
        """File completion callback.
        B3: Buffers log messages and flushes every 100ms.
        F2: Tracks recently completed files in config."""
        try:
            if conv_file.status == "completed":
                self._log_buffer.append(f"✅ {conv_file.filename}")
                # F2: Add to recent files
                try:
                    from office_converter.utils.config import Config
                    config = Config()
                    config.add_recent_file(conv_file.path)
                except Exception:
                    pass
            else:
                self._log_buffer.append(f"❌ {conv_file.filename}")

            if self._log_flush_job is None:
                self._log_flush_job = self.after(100, self._flush_log_buffer)

            if self.file_panel:
                self.after(0, self.file_panel._refresh_display)
        except Exception as e:
            logger.error(f"On file complete error: {e}")

    def _flush_log_buffer(self):
        """Flush buffered log messages to textbox in a single batch."""
        try:
            self._log_flush_job = None
            if not self._log_buffer:
                return

            timestamp = datetime.now().strftime("%H:%M:%S")
            batch_text = "".join(f"[{timestamp}] {msg}\n" for msg in self._log_buffer)
            self._log_buffer.clear()

            if self.log_textbox:
                self.log_textbox.insert("end", batch_text)
                self.log_textbox.see("end")
            logger.info(f"Batch flushed {len(batch_text)} chars")
        except Exception as e:
            logger.error(f"Flush log buffer error: {e}")

    def _on_error(self, conv_file: ConversionFile, error: Exception):
        """Error callback. B3: Uses log buffer instead of direct after(0)."""
        try:
            self._log_buffer.append(f"❌ {conv_file.filename}: {str(error)[:50]}")
            if self._log_flush_job is None:
                self._log_flush_job = self.after(100, self._flush_log_buffer)
        except Exception as e:
            logger.error(f"On error callback error: {e}")

    def _on_conversion_done(self):
        """Conversion completed."""
        try:
            self.is_converting = False

            elapsed = time.time() - self.conversion_start_time
            mins, secs = divmod(int(elapsed), 60)
            time_str = f"{mins}m {secs}s" if mins else f"{secs}s"

            completed = 0
            total = 0
            if self.file_panel:
                completed = sum(1 for f in self.file_panel.files if f.status == "completed")
                total = len(self.file_panel.files)

            # Update progress to 100%
            if self.progress_bar:
                self.progress_bar.set(1.0)
            if self.progress_percent:
                self.progress_percent.configure(text="100%", text_color="#22C55E")
            if self.progress_label:
                self.progress_label.configure(text=get_text('completed_files').format(completed, total))
            if self.progress_title:
                self.progress_title.configure(text=get_text('conversion_complete'))
            if self.status_badge:
                self.status_badge.configure(text=get_text('status_done_text'), fg_color="#22C55E")
            if self.elapsed_label:
                self.elapsed_label.configure(text=f"{mins:02d}:{secs:02d}")
            if self.remaining_label:
                self.remaining_label.configure(text="00:00")
            if self.current_file_label:
                self.current_file_label.configure(text=get_text('all_files_done'))

            # Reset convert button
            if self.btn_convert:
                self.btn_convert.configure(state="normal", text=get_text('btn_convert'))

            # Phase 4: Unlock inputs after completion
            self._toggle_inputs(False)

            # Hide progress frame after delay
            self.after(5000, self._hide_progress_frame)

            self._log(get_text('conversion_done_log').format(completed, total, time_str))

            if completed > 0 and self.file_panel and self.file_panel.files:
                folder = self.output_folder or str(Path(self.file_panel.files[0].path).parent)
                if messagebox.askyesno(get_text('conversion_done_title'),
                                       get_text('conversion_done_msg').format(completed, total, time_str)):
                    os.startfile(folder)
        except Exception as e:
            logger.error(f"On conversion done error: {e}")

    def _hide_progress_frame(self):
        """Hide progress frame after completion."""
        try:
            if self.progress_frame:
                self.progress_frame.pack_forget()
            # P3: Hide compact progress, restore convert button
            if hasattr(self, 'compact_progress_frame'):
                self.compact_progress_frame.pack_forget()
            if hasattr(self, 'btn_stop') and self.btn_stop:
                self.btn_stop.pack_forget()
            if hasattr(self, 'btn_convert') and self.btn_convert:
                self.btn_convert.pack(fill="x")
        except Exception:
            pass

    def _update_time_display(self):
        """Update elapsed time display."""
        try:
            if self.is_converting:
                elapsed = time.time() - self.conversion_start_time
                mins, secs = divmod(int(elapsed), 60)

                if self.elapsed_label:
                    self.elapsed_label.configure(text=f"{mins:02d}:{secs:02d}")

                self.update_idletasks()
                self.after(500, self._update_time_display)
        except Exception as e:
            logger.error(f"Update time display error: {e}")
