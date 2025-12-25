"""
Tests for bug fixes in Office Converter.
"""

import pytest
import os
import tempfile


class TestParsePageRange:
    """Tests for parse_page_range signature fix (BUG-001)."""

    def test_parse_page_range_without_total_pages(self):
        """Test that parse_page_range works without total_pages (new optional param)."""
        from office_converter.core.pdf_tools import parse_page_range
        
        # Without total_pages - should work fine
        result = parse_page_range("1-3, 5, 7-10")
        assert result == [0, 1, 2, 4, 6, 7, 8, 9]  # 0-indexed

    def test_parse_page_range_with_total_pages(self):
        """Test that parse_page_range works with total_pages (backward compatible)."""
        from office_converter.core.pdf_tools import parse_page_range
        
        # With total_pages=5, should clamp to valid range
        result = parse_page_range("1-10", 5)
        assert result == [0, 1, 2, 3, 4]  # Only pages 1-5 (0-indexed)

    def test_parse_page_range_empty_string(self):
        """Test empty string returns empty list."""
        from office_converter.core.pdf_tools import parse_page_range
        
        assert parse_page_range("") == []
        assert parse_page_range("   ") == []

    def test_parse_page_range_reversed_range(self):
        """Test reversed ranges like '5-3' are handled correctly."""
        from office_converter.core.pdf_tools import parse_page_range
        
        result = parse_page_range("5-3")
        assert result == [2, 3, 4]  # 0-indexed: pages 3, 4, 5

    def test_parse_page_range_single_page(self):
        """Test single page number."""
        from office_converter.core.pdf_tools import parse_page_range
        
        result = parse_page_range("3")
        assert result == [2]  # 0-indexed


class TestPdfToolsImports:
    """Tests for pdf_tools module consolidation."""

    def test_utils_pdf_tools_imports_from_core(self):
        """Test that utils/pdf_tools re-exports from core/pdf_tools."""
        from office_converter.utils.pdf_tools import HAS_PYMUPDF, parse_page_range
        from office_converter.core.pdf_tools import HAS_PYMUPDF as core_flag
        from office_converter.core.pdf_tools import parse_page_range as core_parse
        
        # Should be the same
        assert HAS_PYMUPDF == core_flag
        assert parse_page_range is core_parse

    def test_all_expected_functions_available_in_utils(self):
        """Test that all expected functions are available in utils/pdf_tools."""
        from office_converter.utils import pdf_tools
        
        expected_funcs = [
            "merge_pdfs",
            "split_pdf",
            "compress_pdf",
            "protect_pdf",
            "post_process_pdf",
            "rasterize_pdf",
            "add_watermark",
            "pdf_to_images",
            "images_to_pdf",
            "parse_page_range",
            "extract_pages",
            "extract_pdf_pages",
            "delete_pages",
            "rotate_pages",
            "reorder_pages",
            "reverse_pages",
        ]
        
        for func_name in expected_funcs:
            assert hasattr(pdf_tools, func_name), f"Missing: {func_name}"


class TestMainWindowButtons:
    """Tests for main_window UI (BUG-002 fix validation)."""

    def test_main_window_imports_without_error(self):
        """Test that main_window can be imported without errors."""
        # This will fail if there are undefined references
        try:
            from office_converter.ui import main_window
            assert hasattr(main_window, 'ConverterApp')
        except ImportError:
            pytest.skip("UI modules require tkinter")


class TestExceptionHandling:
    """Tests for proper exception handling."""

    def test_parse_page_range_handles_invalid_input(self):
        """Test that invalid input doesn't crash."""
        from office_converter.core.pdf_tools import parse_page_range
        
        # Should return empty, not crash
        assert parse_page_range("abc") == []
        assert parse_page_range("1-abc") == []
        assert parse_page_range(None) == [] if parse_page_range.__code__.co_argcount > 0 else True

    def test_merge_pdfs_handles_missing_files(self):
        """Test that merge_pdfs handles missing files gracefully."""
        from office_converter.utils.pdf_tools import merge_pdfs, HAS_PYMUPDF
        
        if not HAS_PYMUPDF:
            pytest.skip("PyMuPDF not installed")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output = os.path.join(tmpdir, "merged.pdf")
            result = merge_pdfs(
                ["/nonexistent/file1.pdf", "/nonexistent/file2.pdf"],
                output
            )
            # Should return error message, not crash
            assert result is not True
