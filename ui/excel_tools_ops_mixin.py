"""
Excel Tools Operations Mixin — Extracted from ExcelToolsDialog.
Handles all Excel processing operations: split, merge, csv, protect, rename.

This mixin reduces excel_tools_ui.py from ~868 LOC to ~600 LOC.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from office_converter.core.excel_tools import (
    split_excel, merge_excel,
    excel_to_csv, csv_to_excel, protect_sheets, unprotect_sheets, rename_sheets
)

logger = logging.getLogger(__name__)


class ExcelToolsOpsMixin:
    """Mixin: Excel processing operations.

    Requires host class to provide:
        self.files, self.is_processing, self.stop_requested,
        self.var_operation, self.var_merge_mode, self.var_skip_header,
        self.var_output_same, self.var_output_folder,
        self.btn_process, self.btn_stop, self.progress_bar, self.lbl_status,
        self._log(), self.after()
    """

    def _process_files(self):
        """Process files in background thread."""
        op = self.var_operation.get()

        if self.var_output_same.get():
            output_dir = None
        else:
            output_dir = self.var_output_folder.get()
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

        try:
            if op == "split":
                self._do_split(output_dir)
            elif op == "merge":
                self._do_merge(output_dir)
            elif op == "to_csv":
                self._do_to_csv(output_dir)
            elif op == "from_csv":
                self._do_from_csv(output_dir)
            elif op == "protect":
                self._do_protect(output_dir)
            elif op == "unprotect":
                self._do_unprotect(output_dir)
            elif op == "rename":
                self._do_rename(output_dir)
        except Exception as e:
            self.after(0, lambda: self._log(f"❌ Lỗi: {e}"))
            logger.error(f"Processing error: {e}")
        finally:
            self.after(0, self._processing_complete)

    def _do_split(self, output_dir: Optional[str]):
        """Split each file."""
        total = len(self.files)
        success_count = 0

        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break

            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])

            file_output_dir = output_dir or os.path.dirname(file_path)

            def on_progress(current, sheet_total, msg):
                self.after(0, lambda m=msg: self._log(f"  {m}"))

            success_files, errors = split_excel(
                file_path,
                output_dir=file_output_dir,
                on_progress=on_progress
            )

            for sf in success_files:
                self.after(0, lambda f=sf: self._log(f"✅ {os.path.basename(f)}"))
                success_count += 1

            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

            self.after(0, lambda i=idx: self.progress_bar.set((i + 1) / total))

        self.after(0, lambda: self._log(f"\n🎉 Hoàn thành! Tạo {success_count} file(s)"))

    def _do_merge(self, output_dir: Optional[str]):
        """Merge files."""
        if len(self.files) < 2:
            self.after(0, lambda: self._log("⚠️ Cần ít nhất 2 file để gộp"))
            return

        first_file = Path(self.files[0])
        if output_dir:
            output_path = Path(output_dir) / f"{first_file.stem}_merged.xlsx"
        else:
            output_path = first_file.parent / f"{first_file.stem}_merged.xlsx"

        self.after(0, lambda: self.lbl_status.configure(text="Đang gộp files..."))

        mode = self.var_merge_mode.get()
        skip_header = self.var_skip_header.get()

        def on_progress(current, total, msg):
            self.after(0, lambda: [
                self.progress_bar.set(current / total),
                self._log(f"  {msg}")
            ])

        result_path, errors = merge_excel(
            self.files, str(output_path), mode=mode,
            skip_header_after_first=skip_header, on_progress=on_progress
        )

        for err in errors:
            self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

        if result_path:
            self.after(0, lambda: self._log(f"\n🎉 Hoàn thành! File: {os.path.basename(result_path)}"))
        else:
            self.after(0, lambda: self._log("❌ Gộp thất bại"))

    def _do_to_csv(self, output_dir: Optional[str]):
        """Export Excel to CSV."""
        total = len(self.files)
        success_count = 0
        encoding = getattr(self, 'var_encoding', None)
        encoding = encoding.get() if encoding else 'utf-8-sig'
        delimiter = getattr(self, 'var_delimiter', None)
        delimiter = delimiter.get() if delimiter else ','

        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break

            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])

            file_output_dir = output_dir or os.path.dirname(file_path)

            success_files, errors = excel_to_csv(
                file_path, output_dir=file_output_dir,
                encoding=encoding, delimiter=delimiter
            )

            for sf in success_files:
                self.after(0, lambda f=sf: self._log(f"✅ {os.path.basename(f)}"))
                success_count += 1

            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

        self.after(0, lambda: self._log(f"\n🎉 Xuất {success_count} file CSV"))

    def _do_from_csv(self, output_dir: Optional[str]):
        """Import CSV to Excel."""
        first_file = Path(self.files[0])
        if output_dir:
            output_path = Path(output_dir) / f"{first_file.stem}_imported.xlsx"
        else:
            output_path = first_file.parent / f"{first_file.stem}_imported.xlsx"

        self.after(0, lambda: self.lbl_status.configure(text="Đang nhập CSV..."))

        def on_progress(current, total, msg):
            self.after(0, lambda: self.progress_bar.set(current / total))

        result_path, errors = csv_to_excel(self.files, str(output_path), on_progress=on_progress)

        for err in errors:
            self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

        if result_path:
            self.after(0, lambda: self._log(f"\n🎉 Hoàn thành! File: {os.path.basename(result_path)}"))

    def _do_protect(self, output_dir: Optional[str]):
        """Protect sheets."""
        total = len(self.files)
        password = getattr(self, 'var_password', None)
        password = password.get() if password else ""

        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break

            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])

            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(file_path).stem}_protected.xlsx")
            else:
                out_path = str(Path(file_path).parent / f"{Path(file_path).stem}_protected.xlsx")

            result, errors = protect_sheets(file_path, out_path, password=password)

            if result:
                self.after(0, lambda f=result: self._log(f"✅ {os.path.basename(f)}"))
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

        self.after(0, lambda: self._log(f"\n🎉 Đã bảo vệ {total} file(s)"))

    def _do_unprotect(self, output_dir: Optional[str]):
        """Unprotect sheets."""
        total = len(self.files)

        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break

            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])

            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(file_path).stem}_unprotected.xlsx")
            else:
                out_path = str(Path(file_path).parent / f"{Path(file_path).stem}_unprotected.xlsx")

            result, errors = unprotect_sheets(file_path, out_path)

            if result:
                self.after(0, lambda f=result: self._log(f"✅ {os.path.basename(f)}"))
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

        self.after(0, lambda: self._log(f"\n🎉 Đã bỏ bảo vệ {total} file(s)"))

    def _do_rename(self, output_dir: Optional[str]):
        """Rename sheets."""
        total = len(self.files)
        prefix = getattr(self, 'var_prefix', None)
        prefix = prefix.get() if prefix else ""
        suffix = getattr(self, 'var_suffix', None)
        suffix = suffix.get() if suffix else ""
        replace_from = getattr(self, 'var_replace_from', None)
        replace_from = replace_from.get() if replace_from else ""
        replace_to = getattr(self, 'var_replace_to', None)
        replace_to = replace_to.get() if replace_to else ""

        for idx, file_path in enumerate(self.files):
            if self.stop_requested:
                break

            basename = os.path.basename(file_path)
            self.after(0, lambda b=basename, i=idx: [
                self.lbl_status.configure(text=f"({i+1}/{total}) {b}"),
                self.progress_bar.set((i + 0.5) / total)
            ])

            if output_dir:
                out_path = os.path.join(output_dir, f"{Path(file_path).stem}_renamed.xlsx")
            else:
                out_path = str(Path(file_path).parent / f"{Path(file_path).stem}_renamed.xlsx")

            result, errors = rename_sheets(
                file_path, out_path,
                prefix=prefix, suffix=suffix,
                replace_from=replace_from, replace_to=replace_to
            )

            if result:
                self.after(0, lambda f=result: self._log(f"✅ {os.path.basename(f)}"))
            for err in errors:
                self.after(0, lambda e=err: self._log(f"⚠️ {e}"))

        self.after(0, lambda: self._log(f"\n🎉 Đã đổi tên sheets trong {total} file(s)"))

    def _processing_complete(self):
        """Called when processing finishes."""
        self.is_processing = False
        self.btn_process.configure(state="normal", text="🚀 THỰC HIỆN")
        self.btn_stop.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text="Hoàn thành")
