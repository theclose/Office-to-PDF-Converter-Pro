"""
Integration tests: Real conversion end-to-end.
Catches OS-specific file lock bugs and COM automation issues.

These tests require Microsoft Office installed.
Marked with @pytest.mark.requires_office — skip gracefully if unavailable.
"""

import os
import shutil
import tempfile
import pytest
from tests.conftest_integration import (
    create_test_docx, create_test_xlsx, create_test_pptx, create_test_pdf
)


def _has_office():
    """Check if Word COM is available."""
    try:
        import win32com.client
        word = win32com.client.Dispatch("Word.Application")
        word.Quit()
        return True
    except Exception:
        return False


requires_office = pytest.mark.skipif(
    not _has_office(),
    reason="Microsoft Office not installed"
)


class TestRealConversion:
    """Tests that do actual file-to-PDF conversion via COM."""

    @requires_office
    def test_convert_docx_to_pdf(self):
        """Convert a real Word document to PDF."""
        from office_converter.converters.word import WordConverter

        docx = create_test_docx(pages=2)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            converter = WordConverter()
            assert converter.initialize(), "Failed to initialize Word"
            success = converter.convert(docx, out)
            assert success is True, "Word conversion failed"
            assert os.path.exists(out)
            assert os.path.getsize(out) > 100  # Not empty/trivial
        finally:
            for f in [docx, out]:
                if os.path.exists(f):
                    os.remove(f)

    @requires_office
    def test_convert_xlsx_to_pdf(self):
        """Convert a real Excel workbook to PDF."""
        from office_converter.converters.excel import ExcelConverter

        xlsx = create_test_xlsx(sheets=2, rows=50)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            converter = ExcelConverter()
            assert converter.initialize(), "Failed to initialize Excel"
            success = converter.convert(xlsx, out)
            assert success is True, "Excel conversion failed"
            assert os.path.exists(out)
            assert os.path.getsize(out) > 100
        finally:
            for f in [xlsx, out]:
                if os.path.exists(f):
                    os.remove(f)

    @requires_office
    def test_convert_pptx_to_pdf(self):
        """Convert a real PowerPoint to PDF."""
        from office_converter.converters.ppt import PPTConverter

        pptx = create_test_pptx(slides=3)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            converter = PPTConverter()
            assert converter.initialize(), "Failed to initialize PPT"
            success = converter.convert(pptx, out)
            assert success is True, "PPT conversion failed"
            assert os.path.exists(out)
            assert os.path.getsize(out) > 100
        finally:
            for f in [pptx, out]:
                if os.path.exists(f):
                    os.remove(f)

    @requires_office
    def test_convert_overwrite_existing_pdf(self):
        """Converting when output PDF already exists must overwrite it."""
        from office_converter.converters.word import WordConverter

        docx = create_test_docx(pages=1)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        # Write dummy content to output to verify it gets overwritten
        with open(out, 'w') as f:
            f.write("placeholder")
        try:
            converter = WordConverter()
            assert converter.initialize(), "Failed to initialize Word"
            success = converter.convert(docx, out)
            assert success is True, "Overwrite conversion failed"
            assert os.path.getsize(out) > 20  # Real PDF, not our placeholder
        finally:
            for f in [docx, out]:
                if os.path.exists(f):
                    os.remove(f)

    @requires_office
    def test_convert_unicode_filename(self):
        """Vietnamese filename conversion must work."""
        try:
            from docx import Document
        except ImportError:
            pytest.skip("python-docx not available")

        from office_converter.converters.word import WordConverter

        # Create file with Vietnamese name
        tmp_dir = tempfile.mkdtemp()
        docx_path = os.path.join(tmp_dir, "báo_cáo_2026.docx")
        doc = Document()
        doc.add_paragraph("Nội dung báo cáo thử nghiệm")
        doc.save(docx_path)

        out_path = os.path.join(tmp_dir, "báo_cáo_2026.pdf")
        try:
            converter = WordConverter()
            assert converter.initialize(), "Failed to initialize Word"
            success = converter.convert(docx_path, out_path)
            assert success is True, "Unicode filename conversion failed"
            assert os.path.exists(out_path)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestConversionEdgeCases:
    """Edge cases that don't require Office COM."""

    def test_convert_readonly_file(self):
        """Conversion must handle read-only input gracefully."""
        pdf = create_test_pdf(pages=1)
        try:
            # Make it read-only
            os.chmod(pdf, 0o444)
            # We can still read it, so compression should work
            from office_converter.core.pdf.compression import compress_pdf
            fd, out = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                success, _ = compress_pdf(pdf, out, quality="high")
                assert isinstance(success, bool)
            finally:
                if os.path.exists(out):
                    os.remove(out)
        finally:
            os.chmod(pdf, 0o644)  # Restore permissions
            if os.path.exists(pdf):
                os.remove(pdf)

    def test_convert_empty_pdf_graceful(self):
        """Processing an empty/corrupt PDF must not crash."""
        from office_converter.core.pdf.compression import compress_pdf

        fd, empty = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            success, _ = compress_pdf(empty, out, quality="medium")
            assert success is False  # Should fail gracefully
        finally:
            for f in [empty, out]:
                if os.path.exists(f):
                    os.remove(f)

    def test_batch_mixed_types_no_crash(self):
        """Creating ConversionFile objects for mixed types must not crash."""
        from office_converter.core.engine import ConversionFile

        files = []
        paths = [
            ("test.docx", ".docx"),
            ("test.xlsx", ".xlsx"),
            ("test.pptx", ".pptx"),
            ("test.pdf", ".pdf"),
        ]
        for name, ext in paths:
            cf = ConversionFile(path=f"C:\\fake\\{name}")
            files.append(cf)
            assert cf.path.endswith(ext)
        assert len(files) == 4
