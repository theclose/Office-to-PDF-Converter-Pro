"""
Phase 3: Converter Factory & Integration Tests
================================================
Verify converter selection, lifecycle, and fallback chain.
All COM calls mocked via sys.modules.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path


# ===========================================================================
# Lazy-import helper
# ===========================================================================

def _get_factory():
    from office_converter.converters.base import get_converter_for_file, get_best_converter, BaseConverter
    return get_converter_for_file, get_best_converter, BaseConverter


# ===========================================================================
# 1. Converter Selection (Factory)
# ===========================================================================

class TestConverterFactory:

    @pytest.mark.parametrize("filename,expected", [
        ("report.xlsx", "ExcelConverter"),
        ("report.xls", "ExcelConverter"),
        ("report.xlsm", "ExcelConverter"),
        ("report.xlsb", "ExcelConverter"),
        ("doc.docx", "WordConverter"),
        ("doc.doc", "WordConverter"),
        ("doc.docm", "WordConverter"),
        ("doc.rtf", "WordConverter"),
        ("slides.pptx", "PPTConverter"),
        ("slides.ppt", "PPTConverter"),
        ("slides.pptm", "PPTConverter"),
        ("slides.ppsx", "PPTConverter"),
        ("slides.pps", "PPTConverter"),
    ])
    def test_factory_returns_correct_converter(self, filename, expected):
        get_converter_for_file, _, _ = _get_factory()
        conv = get_converter_for_file(filename)
        assert conv is not None, f"No converter for {filename}"
        assert conv.__name__ == expected

    @pytest.mark.parametrize("filename", [
        "image.png", "video.mp4", "output.pdf", "unknown.xyz",
    ])
    def test_factory_returns_none_for_unsupported(self, filename):
        get_converter_for_file, _, _ = _get_factory()
        assert get_converter_for_file(filename) is None

    @pytest.mark.parametrize("filename", ["", None])
    def test_factory_handles_invalid_input(self, filename):
        """None and empty string may return None or raise — both acceptable."""
        get_converter_for_file, _, _ = _get_factory()
        try:
            result = get_converter_for_file(filename)
            assert result is None
        except (TypeError, AttributeError, ValueError):
            pass

    def test_factory_case_insensitive(self):
        get_converter_for_file, _, _ = _get_factory()
        for name in ["FILE.XLSX", "File.XlSx", "file.xlsx"]:
            c = get_converter_for_file(name)
            assert c is not None
            assert c.__name__ == "ExcelConverter"

    def test_multiple_dots_in_filename(self):
        get_converter_for_file, _, _ = _get_factory()
        c = get_converter_for_file("my.report.2024.xlsx")
        assert c.__name__ == "ExcelConverter"

    def test_very_long_filename(self):
        get_converter_for_file, _, _ = _get_factory()
        c = get_converter_for_file("a" * 500 + ".docx")
        assert c.__name__ == "WordConverter"

    def test_unicode_filename(self):
        get_converter_for_file, _, _ = _get_factory()
        c = get_converter_for_file("Báo_cáo_2024.xlsx")
        assert c.__name__ == "ExcelConverter"


# ===========================================================================
# 2. ConversionFile data model
# ===========================================================================

class TestConversionFile:

    def test_detect_excel_type(self):
        from office_converter.core.engine import ConversionFile, FileType
        assert ConversionFile(path="report.xlsx").file_type == FileType.EXCEL

    def test_detect_word_type(self):
        from office_converter.core.engine import ConversionFile, FileType
        assert ConversionFile(path="doc.docx").file_type == FileType.WORD

    def test_detect_ppt_type(self):
        from office_converter.core.engine import ConversionFile, FileType
        assert ConversionFile(path="slides.pptx").file_type == FileType.POWERPOINT

    def test_detect_unknown_type(self):
        from office_converter.core.engine import ConversionFile, FileType
        assert ConversionFile(path="readme.xyz").file_type == FileType.UNKNOWN

    def test_filename_property(self):
        from office_converter.core.engine import ConversionFile
        assert ConversionFile(path="/some/path/report.xlsx").filename == "report.xlsx"

    def test_icon_property(self):
        from office_converter.core.engine import ConversionFile
        assert ConversionFile(path="report.xlsx").icon == "📗"

    def test_default_status(self):
        from office_converter.core.engine import ConversionFile
        assert ConversionFile(path="report.xlsx").status == "pending"

    def test_unicode_path(self):
        from office_converter.core.engine import ConversionFile, FileType
        cf = ConversionFile(path="C:/Users/Tùng/Báo_cáo.xlsx")
        assert cf.file_type == FileType.EXCEL
        assert cf.filename == "Báo_cáo.xlsx"


# ===========================================================================
# 3. ConversionOptions
# ===========================================================================

class TestConversionOptions:

    def test_default_values(self):
        from office_converter.core.engine import ConversionOptions
        opts = ConversionOptions()
        assert opts.quality == 0
        assert opts.quality_dpi == 300
        assert opts.scan_mode is False
        assert opts.password is None
        assert opts.page_range is None

    def test_custom_values(self):
        from office_converter.core.engine import ConversionOptions
        opts = ConversionOptions(quality=2, quality_dpi=150, scan_mode=True,
                                   password="secret", page_range="1-5")
        assert opts.quality == 2
        assert opts.quality_dpi == 150
        assert opts.scan_mode is True


# ===========================================================================
# 4. LibreOffice fallback
# ===========================================================================

class TestLibreOfficeConverter:

    @patch('subprocess.run')
    def test_libreoffice_has_convert_method(self, mock_run):
        from office_converter.converters.libreoffice import LibreOfficeConverter
        conv = LibreOfficeConverter()
        assert hasattr(conv, 'convert')
        assert hasattr(conv, 'cleanup')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
