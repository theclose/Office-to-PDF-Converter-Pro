"""
Converter Fallback Chain Integration Tests
Tests: pre-flight validation, PDF output validation, and converter method chains.

Strategy: Use tmpdir for real files, mock only COM calls via _validate_input bypass.
"""

import os
import sys
import pytest
import tempfile
from unittest.mock import patch, MagicMock

# Mock COM modules before imports
sys.modules.setdefault('pythoncom', MagicMock())
sys.modules.setdefault('win32com', MagicMock())
sys.modules.setdefault('win32com.client', MagicMock())

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# WORD CONVERTER PRE-FLIGHT VALIDATION TESTS
# ============================================================================

class TestWordPreFlight:
    """Test Word converter input validation (no COM needed)."""

    def _make_converter(self):
        from office_converter.converters.word import WordConverter
        conv = WordConverter()
        conv._word = MagicMock()
        conv._use_pool = True
        conv._com_owned = False
        return conv

    def test_rejects_nonexistent_file(self):
        """Rejects files that don't exist."""
        conv = self._make_converter()
        result = conv._validate_input("/nonexistent/file.docx")
        assert result is not None  # Error message returned
        assert "not found" in result.lower()

    def test_rejects_empty_file(self, tmp_path):
        """Rejects 0-byte files."""
        f = tmp_path / "empty.docx"
        f.write_bytes(b"")
        conv = self._make_converter()
        result = conv._validate_input(str(f))
        assert result is not None
        assert "empty" in result.lower()

    def test_accepts_valid_file(self, tmp_path):
        """Accepts files with content and valid size."""
        f = tmp_path / "valid.docx"
        f.write_bytes(b"PK" + b"\x00" * 1000)  # Minimal ZIP-like docx
        conv = self._make_converter()
        result = conv._validate_input(str(f))
        assert result is None  # None = valid


# ============================================================================
# EXCEL CONVERTER PRE-FLIGHT VALIDATION TESTS
# ============================================================================

class TestExcelPreFlight:
    """Test Excel converter input validation."""

    def _make_converter(self):
        from office_converter.converters.excel import ExcelConverter
        conv = ExcelConverter()
        conv._excel = MagicMock()
        conv._use_pool = True
        conv._com_owned = False
        return conv

    def test_rejects_nonexistent_file(self):
        """Rejects missing files."""
        conv = self._make_converter()
        result = conv._validate_input("/nonexistent.xlsx")
        assert result is not None
        assert "not found" in result.lower()

    def test_rejects_empty_file(self, tmp_path):
        """Rejects 0-byte files."""
        f = tmp_path / "empty.xlsx"
        f.write_bytes(b"")
        conv = self._make_converter()
        result = conv._validate_input(str(f))
        assert result is not None

    def test_accepts_valid_file(self, tmp_path):
        """Accepts valid-sized files."""
        f = tmp_path / "valid.xlsx"
        f.write_bytes(b"PK" + b"\x00" * 500)
        conv = self._make_converter()
        result = conv._validate_input(str(f))
        assert result is None


# ============================================================================
# PPT CONVERTER PRE-FLIGHT VALIDATION TESTS
# ============================================================================

class TestPPTPreFlight:
    """Test PPT converter input validation."""

    def _make_converter(self):
        from office_converter.converters.ppt import PPTConverter
        conv = PPTConverter()
        conv._ppt = MagicMock()
        conv._use_pool = True
        conv._com_owned = False
        return conv

    def test_rejects_nonexistent_file(self):
        """Rejects missing files."""
        conv = self._make_converter()
        result = conv._validate_input("/nonexistent.pptx")
        assert result is not None

    def test_rejects_empty_file(self, tmp_path):
        """Rejects 0-byte files."""
        f = tmp_path / "empty.pptx"
        f.write_bytes(b"")
        conv = self._make_converter()
        result = conv._validate_input(str(f))
        assert result is not None

    def test_accepts_valid_file(self, tmp_path):
        """Accepts valid files."""
        f = tmp_path / "valid.pptx"
        f.write_bytes(b"PK" + b"\x00" * 500)
        conv = self._make_converter()
        result = conv._validate_input(str(f))
        assert result is None

    def test_rejects_oversized_file(self, tmp_path):
        """Pre-flight rejects >500MB files (simulated with getsize mock)."""
        f = tmp_path / "huge.pptx"
        f.write_bytes(b"PK" + b"\x00" * 10)
        conv = self._make_converter()
        with patch('os.path.getsize', return_value=600 * 1024 * 1024):
            result = conv._validate_input(str(f))
        assert result is not None
        assert "too large" in result.lower()


# ============================================================================
# LIBREOFFICE VALIDATION TESTS
# ============================================================================

class TestLibreOfficeValidation:
    """Test M2: LibreOffice converter input validation."""

    def test_rejects_nonexistent(self):
        """Rejects missing files."""
        from office_converter.converters.libreoffice import LibreOfficeConverter
        conv = LibreOfficeConverter()
        conv._soffice_path = "/usr/bin/soffice"
        result = conv.convert("/nonexistent.docx", "out.pdf")
        assert result is False

    def test_rejects_empty(self, tmp_path):
        """Rejects 0-byte files."""
        from office_converter.converters.libreoffice import LibreOfficeConverter
        f = tmp_path / "empty.docx"
        f.write_bytes(b"")
        conv = LibreOfficeConverter()
        conv._soffice_path = "/usr/bin/soffice"
        result = conv.convert(str(f), str(tmp_path / "out.pdf"))
        assert result is False


# ============================================================================
# PDF OUTPUT VALIDATION TESTS
# ============================================================================

class TestPDFOutputValidation:
    """Test _validate_pdf_output static method in BaseConverter."""

    def test_valid_pdf(self, tmp_path):
        """Valid PDF with pages passes validation."""
        from office_converter.converters.base import BaseConverter
        import fitz
        pdf_path = str(tmp_path / "valid.pdf")
        doc = fitz.open()
        doc.new_page()
        doc.save(pdf_path)
        doc.close()
        assert BaseConverter._validate_pdf_output(pdf_path) is True

    def test_missing_file(self):
        """Missing file fails validation."""
        from office_converter.converters.base import BaseConverter
        assert BaseConverter._validate_pdf_output("/nonexistent/file.pdf") is False

    def test_tiny_file(self, tmp_path):
        """File too small (<100 bytes) fails."""
        from office_converter.converters.base import BaseConverter
        tiny = tmp_path / "tiny.pdf"
        tiny.write_bytes(b"tiny")
        assert BaseConverter._validate_pdf_output(str(tiny)) is False

    def test_corrupt_file(self, tmp_path):
        """Corrupt (non-PDF) content fails."""
        from office_converter.converters.base import BaseConverter
        bad = tmp_path / "corrupt.pdf"
        bad.write_bytes(b"This is not a PDF " * 20)
        assert BaseConverter._validate_pdf_output(str(bad)) is False


# ============================================================================
# CONFIG THREAD-SAFETY TEST (M3)
# ============================================================================

class TestConfigThreadSafety:
    """Test M3: config.py save() is thread-safe."""

    def test_save_has_lock(self):
        """Config class has _save_lock attribute."""
        from office_converter.utils.config import Config
        assert hasattr(Config, '_save_lock')
        import threading
        assert isinstance(Config._save_lock, type(threading.Lock()))
