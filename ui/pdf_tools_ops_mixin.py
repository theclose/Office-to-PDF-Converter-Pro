"""
PDF Tools Operations Mixin — Extracted from PDFToolsDialogPro.
Handles all PDF processing logic: batch processing, per-operation execution,
merge, and completion callbacks.

This mixin reduces pdf_tools_pro.py from ~1136 LOC to ~840 LOC.
"""

import os
import logging
from office_converter.utils.localization import get_text
from tkinter import filedialog, messagebox

from office_converter.core import pdf_tools

logger = logging.getLogger(__name__)


class PDFToolsOpsMixin:
    """Mixin: PDF processing operations.

    Requires host class to provide:
        self.files, self.is_processing, self.stop_requested,
        self.var_operation, self.var_quality, self.var_rotation,
        self.var_page_range, self.var_watermark_text, self.var_password,
        self.var_dpi, self.var_simulate_scan, self.var_image_format,
        self.var_combine_pages, self.var_custom_jpeg, self.var_custom_dpi,
        self.var_output_same, self.var_output_folder,
        self.compression_results, self.btn_process, self.btn_stop,
        self.progress_bar, self.lbl_status, self.log_textbox,
        self._log(), self._refresh_file_list(), self.after()
    """

    def _process_files(self):
        """Process files in background thread."""
        op = self.var_operation.get()
        total = len(self.files)
        success = 0

        # Get output folder
        if self.var_output_same.get():
            output_folder = None
        else:
            output_folder = self.var_output_folder.get()
            if output_folder:
                os.makedirs(output_folder, exist_ok=True)

        # Get suffix
        suffixes = {
            "compress": "_compressed",
            "smart_compress": "_smart_compressed",
            "rotate": "_rotated",
            "extract": "_extracted",
            "delete": "_deleted",
            "reverse": "_reversed",
            "watermark": "_watermarked",
            "protect": "_protected",
            "pdf_to_img": "",
            "split": "_split",
            "img_to_pdf": ".pdf",
            "ocr": "_ocr",
            "rasterize": "_rasterized",
            "scanmode": "_scanned",
        }
        suffix = suffixes.get(op, "_output")

        for i, input_path in enumerate(self.files):
            if self.stop_requested:
                break

            basename = os.path.basename(input_path)
            name, ext = os.path.splitext(basename)

            # Determine output path
            if output_folder:
                if op == "pdf_to_img":
                    output_path = output_folder
                else:
                    output_path = os.path.join(output_folder, name + suffix + ".pdf")
            else:
                parent = os.path.dirname(input_path)
                if op == "pdf_to_img":
                    output_path = parent
                else:
                    output_path = os.path.join(parent, name + suffix + ".pdf")

            # Update status
            self.after(0, lambda b=basename, idx=i+1: [
                self.lbl_status.configure(text=f"({idx}/{total}) {b}"),
                self.progress_bar.set(idx / total)
            ])

            try:
                result = self._execute_operation(op, input_path, output_path)
                if result:
                    success += 1
                    self.after(0, lambda b=basename: self._log(f"✅ {b}"))
                else:
                    self.after(0, lambda b=basename: self._log(f"❌ {b}"))
            except Exception as e:
                self.after(0, lambda b=basename, err=str(e): self._log(f"❌ {b}: {err}"))

        self.after(0, lambda: self._on_done(success, total))

    def _execute_operation(self, op: str, input_path: str, output_path: str) -> bool:
        """Execute single operation."""
        try:
            if op == "compress":
                orig_size = os.path.getsize(input_path)
                quality = self.var_quality.get()

                def on_progress(current, total, percent):
                    self.after(0, lambda c=current, t=total, p=percent: self._log(
                        f"   📄 Page {c}/{t} ({p*100:.0f}%)"
                    ))

                if quality == "custom":
                    try:
                        custom_jpeg = max(1, min(100, int(self.var_custom_jpeg.get() or "75")))
                    except ValueError:
                        custom_jpeg = 75
                    try:
                        custom_dpi = max(72, min(300, int(self.var_custom_dpi.get() or "150")))
                    except ValueError:
                        custom_dpi = 150

                    result, reduction, stats = pdf_tools.compress_pdf_advanced(
                        input_path, output_path,
                        quality="medium",
                        target_dpi=custom_dpi,
                        jpeg_quality=custom_jpeg,
                        progress_callback=on_progress
                    )
                elif quality == "target_size":
                    try:
                        target_kb = max(50, int(self.var_target_kb.get() or "1000"))
                    except ValueError:
                        target_kb = 1000
                    
                    self.after(0, lambda: self._log(f"   🎯 Target: ≤{target_kb} KB"))
                    
                    result, reduction, stats = pdf_tools.compress_to_target_size(
                        input_path, output_path,
                        target_kb=target_kb,
                        cancel_check=lambda: self.stop_requested,
                    )
                    
                    # SSIM quality check
                    if result and os.path.exists(output_path):
                        try:
                            ssim_result = pdf_tools.compute_ssim(input_path, output_path)
                            ssim_val = ssim_result.get("ssim", 0)
                            ssim_label = ssim_result.get("quality_label", "unknown")
                            self.after(0, lambda s=ssim_val, l=ssim_label: self._log(
                                f"   📊 SSIM: {s:.4f} ({l})"
                            ))
                        except Exception:
                            pass
                    
                    if stats.get("target_achieved"):
                        self.after(0, lambda s=stats: self._log(
                            f"   ✅ Đạt mục tiêu: {s.get('final_kb', 0):.0f}KB ≤ {target_kb}KB (quality={s.get('quality_used', '?')}%, {s.get('iterations', 0)} iterations)"
                        ))
                    else:
                        self.after(0, lambda s=stats: self._log(
                            f"   ⚠️ Best effort: {s.get('final_kb', 0):.0f}KB (target {target_kb}KB không đạt được)"
                        ))
                else:
                    result, reduction, stats = pdf_tools.compress_pdf_advanced(
                        input_path, output_path,
                        quality=quality,
                        progress_callback=on_progress
                    )
                if result and os.path.exists(output_path):
                    new_size = os.path.getsize(output_path)
                    self.compression_results[input_path] = (orig_size, new_size)
                    self.after(0, lambda s=stats: self._log(
                        f"   ✅ {s.get('images_optimized', 0)} pages | {s.get('reduction_percent', 0):.1f}% smaller"
                    ))
                    self.after(0, self._refresh_file_list)
                return result

            elif op == "smart_compress":
                orig_size = os.path.getsize(input_path)

                def on_progress(current, total, percent):
                    self.after(0, lambda c=current, t=total, p=percent: self._log(
                        f"   🖼️ Image {c}/{t} ({p*100:.0f}%)"
                    ))

                result, reduction, stats = pdf_tools.compress_pdf_smart(
                    input_path, output_path,
                    quality=self.var_quality.get(),
                    progress_callback=on_progress
                )
                if result and os.path.exists(output_path):
                    new_size = os.path.getsize(output_path)
                    self.compression_results[input_path] = (orig_size, new_size)
                    self.after(0, lambda s=stats: self._log(
                        f"   ✅ {s.get('reduction_percent', 0):.1f}% smaller | Images: {s.get('images_optimized', 0)}/{s.get('images_found', 0)} | Text: ✓ Preserved"
                    ))
                    self.after(0, self._refresh_file_list)
                return result

            elif op == "protect":
                pwd = self.var_password.get()
                return pdf_tools.protect_pdf(input_path, output_path, pwd) if pwd else False
            elif op == "rotate":
                return pdf_tools.rotate_pages(input_path, output_path, self.var_rotation.get())
            elif op == "extract":
                ok, _ = pdf_tools.extract_pages(input_path, output_path, self.var_page_range.get())
                return ok
            elif op == "delete":
                ok, _ = pdf_tools.delete_pages(input_path, output_path, self.var_page_range.get())
                return ok
            elif op == "reverse":
                return pdf_tools.reverse_pages(input_path, output_path)
            elif op == "watermark":
                return pdf_tools.add_watermark(input_path, output_path, self.var_watermark_text.get())
            elif op == "pdf_to_img":
                if self.var_combine_pages.get():
                    ext = self.var_image_format.get()
                    single_output = output_path + f"_combined.{ext}"
                    success, stats = pdf_tools.pdf_to_single_image(
                        input_path, single_output,
                        dpi=self.var_dpi.get(),
                        image_format=self.var_image_format.get()
                    )
                    if success:
                        self.after(0, lambda s=stats: self._log(
                            f"   ✅ {s['pages']} pages → {s['width']}x{s['height']}px ({s['file_size']//1024} KB)"
                        ))
                    return success
                else:
                    imgs = pdf_tools.pdf_to_images(input_path, output_path, self.var_dpi.get(), self.var_image_format.get())
                    return len(imgs) > 0
            elif op == "split":
                split_mode = self.var_split_mode.get()
                if split_mode == "by_parts":
                    try:
                        num_parts = max(2, int(self.var_split_num.get() or "3"))
                    except ValueError:
                        num_parts = 3
                    self.after(0, lambda n=num_parts: self._log(f"   📦 Tách thành {n} file"))
                    return pdf_tools.split_pdf_by_parts(input_path, output_path, num_parts)
                elif split_mode == "by_pages":
                    try:
                        pages_per = max(1, int(self.var_split_num.get() or "5"))
                    except ValueError:
                        pages_per = 5
                    self.after(0, lambda n=pages_per: self._log(f"   📑 Mỗi file {n} trang"))
                    return pdf_tools.split_pdf_by_pages_per_file(input_path, output_path, pages_per)
                else:
                    return pdf_tools.split_pdf(input_path, output_path)
            elif op == "img_to_pdf":
                return pdf_tools.images_to_pdf([input_path], output_path)
            elif op == "ocr":
                from office_converter.utils.ocr import ocr_pdf_to_searchable, is_ocr_available
                if not is_ocr_available():
                    return False
                return ocr_pdf_to_searchable(input_path, output_path, lang=None)
            elif op == "rasterize":
                return pdf_tools.rasterize_pdf(
                    input_path,
                    output_path,
                    self.var_dpi.get(),
                    simulate_scan=self.var_simulate_scan.get()
                )
            elif op == "scanmode":
                dpi = getattr(self, 'var_scan_dpi', None)
                dpi = dpi.get() if dpi else 150
                return pdf_tools.rasterize_pdf(
                    input_path,
                    output_path,
                    dpi,
                    simulate_scan=True
                )
            return False
        except Exception as e:
            logger.error(f"Operation {op} failed: {e}")
            return False

    def _do_merge(self):
        """Merge PDFs."""
        if len(self.files) < 2:
            messagebox.showwarning(get_text("warning"), get_text("need_2_files"))
            return

        if self.var_output_same.get():
            output = os.path.join(os.path.dirname(self.files[0]), "merged.pdf")
            counter = 1
            while os.path.exists(output):
                output = os.path.join(os.path.dirname(self.files[0]), f"merged_{counter}.pdf")
                counter += 1
        else:
            output = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF", "*.pdf")],
                initialfile="merged.pdf"
            )
            if not output:
                return

        self._log(f"📎 Gộp {len(self.files)} files...")
        result = pdf_tools.merge_pdfs(self.files, output)

        if result:
            self._log(get_text("pt_merged_ok").format(os.path.basename(output)))
            output_folder = os.path.dirname(output)
            open_folder = messagebox.askyesno(
                "✅ Thành công",
                f"Đã gộp {len(self.files)} files!\n\n"
                f"File: {os.path.basename(output)}\n\n"
                f"Mở thư mục chứa file?",
                parent=self
            )
            if open_folder:
                try:
                    os.startfile(output_folder)
                except Exception as e:
                    self._log(get_text("pt_open_folder_err").format(e))
        else:
            self._log(get_text("pt_merge_failed"))
            messagebox.showerror("Lỗi", "Không thể gộp PDF!")

    def _on_done(self, success: int, total: int):
        """Processing complete."""
        self.is_processing = False
        self.btn_process.configure(state="normal", text="🚀 THỰC HIỆN")
        self.btn_stop.configure(state="disabled")
        self.progress_bar.set(1.0)
        self.lbl_status.configure(text=f"✅ Xong: {success}/{total}")
        self._log(get_text("pt_batch_done").format(success=success, total=total))

        if success > 0:
            if self.var_output_same.get():
                if self.files:
                    output_folder = os.path.dirname(self.files[0])
                else:
                    output_folder = None
            else:
                output_folder = self.var_output_folder.get()

            if output_folder and os.path.exists(output_folder):
                result = messagebox.askyesno(
                    "✅ Hoàn thành",
                    f"Đã xử lý thành công {success}/{total} files.\n\n"
                    f"Mở thư mục chứa file đã xử lý?",
                    parent=self
                )
                if result:
                    try:
                        os.startfile(output_folder)
                    except Exception as e:
                        self._log(get_text("pt_open_folder_err").format(e))
            else:
                messagebox.showinfo(
                    "✅ Hoàn thành",
                    f"Đã xử lý thành công {success}/{total} files.",
                    parent=self
                )
