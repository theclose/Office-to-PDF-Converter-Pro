"""
Phase 4: Engine, Threading & Edge Cases
=========================================
Verify ConversionEngine orchestration, force stop, watchdog, and edge cases.
All COM/subprocess calls mocked.
"""

import sys
import os
import pytest
import threading
import time
from unittest.mock import patch, MagicMock, call
from pathlib import Path


# ===========================================================================
# Lazy-import helper (conftest.py adds project root to sys.path)
# ===========================================================================

def _get_engine_classes():
    """Import engine classes lazily (after conftest adds sys.path)."""
    from office_converter.core.engine import (
        ConversionEngine, ConversionFile, ConversionOptions, FileType,
        FILE_EXTENSIONS
    )
    return ConversionEngine, ConversionFile, ConversionOptions, FileType, FILE_EXTENSIONS


@pytest.fixture
def engine():
    """Create ConversionEngine with mock callbacks."""
    ConversionEngine = _get_engine_classes()[0]
    progress_calls = []
    complete_calls = []
    error_calls = []

    with patch('office_converter.core.engine.RecentFilesDB'):
        eng = ConversionEngine(
            on_progress=lambda i, total, fn: progress_calls.append((i, total, fn)),
            on_file_complete=lambda cf: complete_calls.append(cf),
            on_error=lambda cf, err: error_calls.append((cf, err)),
        )
    eng._progress_calls = progress_calls
    eng._complete_calls = complete_calls
    eng._error_calls = error_calls
    return eng


@pytest.fixture
def sample_files(tmp_path):
    """Create sample test files."""
    _, ConversionFile, _, _, _ = _get_engine_classes()
    files = []
    for name in ["report.xlsx", "doc.docx", "slides.pptx"]:
        f = tmp_path / name
        f.write_bytes(b"dummy content")
        files.append(ConversionFile(path=str(f)))
    return files


# ===========================================================================
# 1. Engine batch conversion
# ===========================================================================

class TestEngineBatch:

    @patch('office_converter.core.engine.record_watchdog_conversion')
    @patch('office_converter.core.engine.start_watchdog')
    @patch('office_converter.core.engine.stop_watchdog')
    @patch('office_converter.core.engine.get_converter_for_file')
    @patch('pythoncom.CoInitialize')
    def test_batch_calls_progress(self, mock_coinit, mock_get_conv,
                                    mock_stop_wd, mock_start_wd,
                                    mock_record, engine, sample_files):
        mock_conv_cls = MagicMock()
        mock_conv_instance = MagicMock()
        mock_conv_instance.convert.return_value = True
        mock_conv_cls.return_value = mock_conv_instance
        mock_get_conv.return_value = mock_conv_cls

        _, _, ConversionOptions, _, _ = _get_engine_classes()
        engine.convert_batch(sample_files, ConversionOptions())
        assert len(engine._progress_calls) == 3

    @patch('office_converter.core.engine.record_watchdog_conversion')
    @patch('office_converter.core.engine.start_watchdog')
    @patch('office_converter.core.engine.stop_watchdog')
    @patch('office_converter.core.engine.get_converter_for_file')
    @patch('pythoncom.CoInitialize')
    def test_batch_0_files_no_crash(self, mock_coinit, mock_get_conv,
                                     mock_stop_wd, mock_start_wd,
                                     mock_record, engine):
        _, _, ConversionOptions, _, _ = _get_engine_classes()
        engine.convert_batch([], ConversionOptions())
        assert len(engine._progress_calls) == 0


# ===========================================================================
# 2. Engine stop flag
# ===========================================================================

class TestEngineStop:

    def test_stop_sets_flag(self, engine):
        engine.stop()
        assert engine._stop_requested is True

    def test_stop_event_set(self, engine):
        engine.stop()
        assert engine._stop_event.is_set()

    def test_reset_clears_stop(self, engine):
        engine.stop()
        engine.reset()
        assert engine._stop_requested is False
        assert not engine._stop_event.is_set()


# ===========================================================================
# 3. Force stop
# ===========================================================================

class TestForceStop:

    @patch('subprocess.run')
    def test_force_stop_kills_office(self, mock_run, engine):
        mock_converter = MagicMock()
        engine._current_converter = mock_converter
        engine.stop(force=True)

        # F1: cleanup() must NOT be called cross-thread (STA violation)
        mock_converter.cleanup.assert_not_called()
        # Reference should be nulled
        assert engine._current_converter is None
        # taskkill should handle process termination
        for proc in ['EXCEL.EXE', 'WINWORD.EXE', 'POWERPNT.EXE']:
            mock_run.assert_any_call(
                ['taskkill', '/F', '/IM', proc],
                capture_output=True, timeout=5
            )

    @patch('subprocess.run')
    def test_force_stop_cleans_incomplete(self, mock_run, engine, tmp_path):
        partial_file = tmp_path / "output.pdf"
        partial_file.write_bytes(b"partial")
        engine._current_output_path = str(partial_file)
        engine._force_stop()
        assert not partial_file.exists()


# ===========================================================================
# 4. ConversionFile edge cases
# ===========================================================================

class TestConversionFileEdges:

    def test_unknown_extension(self):
        _, ConversionFile, _, FileType, _ = _get_engine_classes()
        assert ConversionFile(path="file.xyz").file_type == FileType.UNKNOWN

    def test_unicode_filename(self):
        _, ConversionFile, _, FileType, _ = _get_engine_classes()
        cf = ConversionFile(path="C:/Báo_cáo_2024.xlsx")
        assert cf.file_type == FileType.EXCEL

    def test_very_long_path(self):
        _, ConversionFile, _, FileType, _ = _get_engine_classes()
        cf = ConversionFile(path="C:/" + "a" * 250 + ".docx")
        assert cf.file_type == FileType.WORD

    def test_no_extension(self):
        _, ConversionFile, _, FileType, _ = _get_engine_classes()
        assert ConversionFile(path="README").file_type == FileType.UNKNOWN


# ===========================================================================
# 5. P8 Regression: Version exists
# ===========================================================================

class TestP8VersionMismatch:

    def test_version_exists(self):
        from office_converter import __version__
        assert __version__ is not None
        assert isinstance(__version__, str)

    def test_version_format(self):
        from office_converter import __version__
        assert len(__version__.split(".")) >= 2


# ===========================================================================
# 6. P7 Regression: PDF tools re-export identity
# ===========================================================================

class TestP7PdfToolsIdentity:

    def test_parse_page_range_identity(self):
        from office_converter.utils.pdf_tools import parse_page_range as u
        from office_converter.core.pdf_tools import parse_page_range as c
        assert u is c

    def test_has_pymupdf_same(self):
        from office_converter.utils.pdf_tools import HAS_PYMUPDF as u
        from office_converter.core.pdf_tools import HAS_PYMUPDF as c
        assert u == c


# ===========================================================================
# 7. FILE_EXTENSIONS completeness
# ===========================================================================

class TestFileExtensions:

    def test_all_excel_extensions(self):
        _, _, _, FileType, FILE_EXTENSIONS = _get_engine_classes()
        for ext in [".xlsx", ".xls", ".xlsm", ".xlsb"]:
            assert ext in FILE_EXTENSIONS[FileType.EXCEL]

    def test_all_word_extensions(self):
        _, _, _, FileType, FILE_EXTENSIONS = _get_engine_classes()
        for ext in [".docx", ".doc", ".docm", ".rtf"]:
            assert ext in FILE_EXTENSIONS[FileType.WORD]

    def test_all_ppt_extensions(self):
        _, _, _, FileType, FILE_EXTENSIONS = _get_engine_classes()
        for ext in [".pptx", ".ppt", ".pptm", ".ppsx", ".pps"]:
            assert ext in FILE_EXTENSIONS[FileType.POWERPOINT]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
