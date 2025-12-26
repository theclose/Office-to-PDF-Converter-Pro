"""
Critical Tests for Converters - Enhanced Manual Implementation
===============================================================
Tests for core converter functionality with real scenarios.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
import os
import tempfile
from pathlib import Path

# Import actual converters
from converters.base import (
    get_converter_for_file,
    get_best_converter,
    BaseConverter,
    ensure_com_initialized,
    release_com
)


# ==================== COM Initialization Tests ====================

class TestCOMManagement:
    """Critical tests for COM initialization and cleanup."""
    
    @patch('converters.base.pythoncom')
    def test_ensure_com_initialized_creates_new_thread(self, mock_pythoncom):
        """Test COM initialization creates apartment thread."""
        mock_pythoncom.CoInitialize.return_value = None
        
        ensure_com_initialized()
        
        mock_pythoncom.CoInitialize.assert_called_once()
        
    @patch('converters.base.pythoncom')
    def test_ensure_com_handles_already_initialized(self, mock_pythoncom):
        """Test COM handles S_FALSE (already initialized)."""
        import pywintypes
        mock_pythoncom.CoInitialize.side_effect = pywintypes.com_error(-2147417850, 'CoInitialize', '', None)
        
        # Should not raise
        ensure_com_initialized()
        
    @patch('converters.base.pythoncom')
    def test_release_com_uninitializes(self, mock_pythoncom):
        """Test COM cleanup uninitializes thread."""
        release_com()
        
        mock_pythoncom.CoUninitialize.assert_called_once()


# ==================== Converter Selection Tests ====================

class TestConverterSelection:
    """Critical tests for file-to-converter mapping."""
    
    @pytest.mark.parametrize("filename,expected_name", [
        ("document.xlsx", "ExcelConverter"),
        ("document.xls", "ExcelConverter"),
        ("report.docx", "WordConverter"),
        ("report.doc", "WordConverter"),
        ("presentation.pptx", "PPTConverter"),
        ("presentation.ppt", "PPTConverter"),
        ("document.odt", "LibreOfficeConverter"),
        ("spreadsheet.ods", "LibreOfficeConverter"),
    ])
    def test_get_converter_for_supported_files(self, filename, expected_name):
        """Test correct converter is returned for each file type."""
        converter_class = get_converter_for_file(filename)
        
        assert converter_class is not None, f"No converter for {filename}"
        assert converter_class.__name__ == expected_name
        
    @pytest.mark.parametrize("filename", [
        "image.png",
        "video.mp4",
        "document.pdf",  # PDF is output, not input
        "unknown.xyz",
        "",
        None,
    ])
    def test_get_converter_for_unsupported_files(self, filename):
        """Test None returned for unsupported file types."""
        converter_class = get_converter_for_file(filename)
        
        assert converter_class is None
        
    def test_get_converter_case_insensitive(self):
        """Test file extension matching is case-insensitive."""
        converters = [
            get_converter_for_file("FILE.XLSX"),
            get_converter_for_file("File.XlSx"),
            get_converter_for_file("file.xlsx"),
        ]
        
        # All should return same converter
        assert all(c.__name__ == "ExcelConverter" for c in converters)
        
    def test_get_best_converter_prefers_native(self):
        """Test best_converter prefers native over LibreOffice."""
        # For .xlsx, should prefer ExcelConverter over LibreOfficeConverter
        converter = get_best_converter("test.xlsx")
        
        assert converter.__name__ == "ExcelConverter"
        
    @patch('converters.base.get_converter_for_file')
    def test_get_best_converter_fallback_to_libreoffice(self, mock_get):
        """Test fallback to LibreOffice if native unavailable."""
        # Simulate native converter not available
        mock_get.side_effect = [None, Mock(__name__="LibreOfficeConverter")]
        
        converter = get_best_converter("test.xlsx")
        
        assert mock_get.call_count == 2  # Tried native, then fallback


# ==================== BaseConverter Tests ====================

class TestBaseConverter:
    """Critical tests for base converter abstract class."""
    
    @pytest.fixture
    def mock_converter(self):
        """Create a mock concrete converter."""
        class MockConverter(BaseConverter):
            def supports_file(self, file_path: str) -> bool:
                return file_path.endswith(".mock")
                
            def initialize(self):
                self._initialized = True
                
            def convert(self, input_path: str, output_path: str):
                with open(output_path, 'wb') as f:
                    f.write(b"PDF mock content")
                    
            def cleanup(self):
                self._initialized = False
                
        return MockConverter()
        
    def test_converter_supports_file_check(self, mock_converter):
        """Test file support checking."""
        assert mock_converter.supports_file("test.mock") == True
        assert mock_converter.supports_file("test.other") == False
        
    def test_converter_lifecycle(self, mock_converter, tmp_path):
        """Test full converter lifecycle: init → convert → cleanup."""
        input_file = tmp_path / "input.mock"
        output_file = tmp_path / "output.pdf"
        input_file.write_text("test data")
        
        # Initialize
        mock_converter.initialize()
        assert mock_converter._initialized == True
        
        # Convert
        mock_converter.convert(str(input_file), str(output_file))
        assert output_file.exists()
        
        # Cleanup
        mock_converter.cleanup()
        assert mock_converter._initialized == False
        
    def test_progress_callback_invoked(self, mock_converter, tmp_path):
        """Test progress callback is called during conversion."""
        progress_calls = []
        
        def progress_cb(value):
            progress_calls.append(value)
            
        converter = mock_converter
        converter.progress_callback = progress_cb
        
        input_file = tmp_path / "input.mock"
        output_file = tmp_path / "output.pdf"
        input_file.write_text("test")
        
        converter.convert(str(input_file), str(output_file))
        
        # Should have received progress updates
        assert len(progress_calls) > 0
        assert all(0 <= p <= 100 for p in progress_calls)
        
    def test_log_callback_invoked(self, mock_converter):
        """Test log callback receives messages."""
        log_messages = []
        
        def log_cb(msg):
            log_messages.append(msg)
            
        mock_converter.log_callback = log_cb
        mock_converter.log("Test message")
        
        assert len(log_messages) == 1
        assert "Test message" in log_messages[0]


# ==================== Integration Tests ====================

class TestConverterIntegration:
    """Integration tests for real-world conversion scenarios."""
    
    @pytest.fixture
    def sample_files(self, tmp_path):
        """Create sample test files."""
        # Create dummy files (not real Office docs, just for path testing)
        files = {
            'excel': tmp_path / "test.xlsx",
            'word': tmp_path / "test.docx",
            'ppt': tmp_path / "test.pptx",
        }
        
        for f in files.values():
            f.write_bytes(b"dummy content")  # Not real Office file
            
        return files
        
    def test_converter_handles_missing_input_file(self, mock_converter, tmp_path):
        """Test converter handles gracefully when input doesn't exist."""
        nonexistent = tmp_path / "nonexistent.mock"
        output = tmp_path / "output.pdf"
        
        with pytest.raises(FileNotFoundError):
            mock_converter.convert(str(nonexistent), str(output))
            
    def test_converter_creates_output_directory(self, mock_converter, tmp_path):
        """Test converter creates output dir if it doesn't exist."""
        input_file = tmp_path / "input.mock"
        input_file.write_text("test")
        
        # Output in non-existent subdirectory
        output_file = tmp_path / "subdir" / "output.pdf"
        
        mock_converter.convert(str(input_file), str(output_file))
        
        assert output_file.exists()
        assert output_file.parent.exists()
        
    @patch('converters.base.pythoncom')
    def test_converter_thread_safety(self, mock_pythoncom, mock_converter, tmp_path):
        """Test converter can be used from multiple threads."""
        import threading
        results = []
        
        def convert_in_thread():
            input_f = tmp_path / f"input_{threading.current_thread().name}.mock"
            output_f = tmp_path / f"output_{threading.current_thread().name}.pdf"
            input_f.write_text("test")
            
            mock_converter.convert(str(input_f), str(output_f))
            results.append(output_f.exists())
            
        threads = [threading.Thread(target=convert_in_thread) for _ in range(3)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # All conversions should succeed
        assert all(results)
        assert len(results) == 3


# ==================== Edge Cases & Error Handling ====================

class TestConverterEdgeCases:
    """Edge cases and error handling tests."""
    
    def test_get_converter_with_very_long_filename(self):
        """Test handling of extremely long filenames."""
        long_name = "a" * 500 + ".xlsx"
        converter = get_converter_for_file(long_name)
        
        assert converter.__name__ == "ExcelConverter"
        
    def test_get_converter_with_special_characters(self):
        """Test filenames with special characters."""
        filenames = [
            "文档.xlsx",  # Chinese
            "документ.xlsx",  # Russian
            "file (copy).xlsx",  # Parentheses
            "file-2024.xlsx",  # Dash
        ]
        
        for fname in filenames:
            converter = get_converter_for_file(fname)
            assert converter is not None
            
    def test_converter_with_no_extension(self):
        """Test handling of files without extension."""
        converter = get_converter_for_file("README")
        assert converter is None
        
    def test_converter_with_multiple_dots(self):
        """Test file with multiple dots in name."""
        converter = get_converter_for_file("my.file.name.xlsx")
        assert converter.__name__ == "ExcelConverter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
