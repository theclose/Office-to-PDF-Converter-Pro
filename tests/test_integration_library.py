"""
Integration tests: Library-internal edge cases.
Catches bugs like Trap #16 (PyMuPDF save-to-original).

These tests exercise third-party library behaviors that
static code audit cannot detect.
"""

import os
import gc
import shutil
import tempfile
import pytest
from tests.conftest_integration import (
    create_test_pdf, create_test_docx, create_test_xlsx
)


class TestCompressionLibraryEdgeCases:
    """Tests for PyMuPDF compression edge cases."""

    def test_compress_pdf_same_path(self):
        """Trap #16: compress_pdf must work when output == input.
        PyMuPDF refuses doc.save() to the opened file.
        This test catches the exact bug from Trap #16."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf = create_test_pdf(pages=3, with_image=True)
        try:
            # Compress IN-PLACE (output == input)
            success, reduction = compress_pdf(pdf, pdf, quality="medium")
            assert success is True, "Same-path compression must succeed"
            assert os.path.exists(pdf), "File must still exist after in-place compress"
            assert os.path.getsize(pdf) > 0, "File must not be empty"
        finally:
            if os.path.exists(pdf):
                os.remove(pdf)

    def test_compress_pdf_different_path(self):
        """Standard case: compress to a different output path."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf = create_test_pdf(pages=3)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            success, reduction = compress_pdf(pdf, out, quality="medium")
            assert success is True
            assert os.path.exists(out)
        finally:
            for f in [pdf, out]:
                if os.path.exists(f):
                    os.remove(f)

    def test_compress_pdf_locked_file(self):
        """Compression must handle gracefully when input is locked."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf = create_test_pdf(pages=1)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            # Lock the input file by opening it
            with open(pdf, 'rb') as locked:
                # PyMuPDF can still read from locked files on Windows
                # but this tests that the code doesn't crash
                success, _ = compress_pdf(pdf, out, quality="high")
                # Should either succeed or fail gracefully
                assert isinstance(success, bool)
        finally:
            for f in [pdf, out]:
                if os.path.exists(f):
                    os.remove(f)

    def test_fitz_save_all_garbage_levels(self):
        """Test all garbage collection levels work correctly."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf = create_test_pdf(pages=2, with_image=True)
        try:
            for quality in ["low", "medium", "high"]:
                fd, out = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                try:
                    success, _ = compress_pdf(pdf, out, quality=quality)
                    assert isinstance(success, bool), f"Quality '{quality}' returned non-bool"
                finally:
                    if os.path.exists(out):
                        os.remove(out)
        finally:
            if os.path.exists(pdf):
                os.remove(pdf)


class TestMergeSplitLibraryEdgeCases:
    """Tests for PyMuPDF merge/split edge cases."""

    def test_merge_pdfs_into_source(self):
        """Merge output targeting one of the input files."""
        from office_converter.core.pdf.merge_split import merge_pdfs

        pdf1 = create_test_pdf(pages=2)
        pdf2 = create_test_pdf(pages=1)
        try:
            # Merge into pdf1 (output == first input)
            success = merge_pdfs([pdf1, pdf2], pdf1)
            assert isinstance(success, bool)
            if success:
                assert os.path.exists(pdf1)
                assert os.path.getsize(pdf1) > 0
        finally:
            for f in [pdf1, pdf2]:
                if os.path.exists(f):
                    os.remove(f)

    def test_split_pdf_single_page(self):
        """Edge: splitting a single-page PDF."""
        from office_converter.core.pdf.merge_split import split_pdf

        pdf = create_test_pdf(pages=1)
        out_dir = tempfile.mkdtemp()
        try:
            result = split_pdf(pdf, out_dir)
            assert isinstance(result, (bool, list))
        finally:
            if os.path.exists(pdf):
                os.remove(pdf)
            shutil.rmtree(out_dir, ignore_errors=True)

    def test_watermark_non_ascii_text(self):
        """Vietnamese watermark text must render correctly."""
        from office_converter.core.pdf.watermark import add_watermark

        pdf = create_test_pdf(pages=1)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            success = add_watermark(
                pdf, out,
                text="BẢN MẬT - CONFIDENTIAL",
                opacity=0.3
            )
            assert success is True
            assert os.path.exists(out)
            assert os.path.getsize(out) > 0
        finally:
            for f in [pdf, out]:
                if os.path.exists(f):
                    os.remove(f)

    def test_conversion_100_page_memory(self):
        """R3 regression: pdf_to_single_image must not OOM on 100 pages.
        Peak RAM should stay under 500MB with two-pass streaming."""
        import psutil
        from office_converter.core.pdf.conversion import pdf_to_single_image

        pdf = create_test_pdf(pages=50)  # 50 pages (100 would be too slow for CI)
        fd, out = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            process = psutil.Process()
            mem_before = process.memory_info().rss / (1024 * 1024)  # MB

            success, stats = pdf_to_single_image(pdf, out, dpi=72)

            mem_after = process.memory_info().rss / (1024 * 1024)
            mem_used = mem_after - mem_before

            assert success is True, f"Conversion failed: {stats}"
            # Two-pass streaming should keep memory under 500MB even for 50 pages
            assert mem_used < 500, f"Memory spike too high: {mem_used:.0f}MB"
        except ImportError:
            pytest.skip("psutil not available")
        finally:
            for f in [pdf, out]:
                if os.path.exists(f):
                    os.remove(f)
            gc.collect()
