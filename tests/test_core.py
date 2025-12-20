"""Unit tests for Office Converter."""


class TestImports:
    """Test that all modules import correctly."""

    def test_import_converters(self):
        from office_converter.converters import ExcelConverter, WordConverter, PPTConverter
        assert ExcelConverter is not None
        assert WordConverter is not None
        assert PPTConverter is not None

    def test_import_utils(self):
        from office_converter.utils import Config, get_pool, setup_logging
        assert Config is not None
        assert get_pool is not None
        assert setup_logging is not None

    def test_import_pdf_tools(self):
        from office_converter.utils.pdf_tools import merge_pdfs, HAS_PYMUPDF
        assert merge_pdfs is not None
        assert isinstance(HAS_PYMUPDF, bool)


class TestConfig:
    """Test configuration management."""

    def test_config_singleton(self, temp_dir):
        from office_converter.utils.config import Config
        # Reset singleton for testing
        Config._instance = None
        Config._initialized = False

        cfg1 = Config(str(temp_dir / "test_config.json"))
        cfg2 = Config()
        assert cfg1 is cfg2

    def test_config_defaults(self, temp_dir):
        from office_converter.utils.config import Config
        Config._instance = None
        Config._initialized = False

        cfg = Config(str(temp_dir / "test_config.json"))
        assert cfg.language == "vi"
        assert cfg.pdf_quality == 0

    def test_config_deepcopy(self, temp_dir):
        """Verify nested dicts are deep copied."""
        from office_converter.utils.config import Config, DEFAULT_CONFIG
        Config._instance = None
        Config._initialized = False

        cfg = Config(str(temp_dir / "test_config.json"))
        # Modify nested dict
        cfg._data["metadata"]["author"] = "Test Author"

        # DEFAULT_CONFIG should be unchanged
        assert DEFAULT_CONFIG["metadata"]["author"] == ""


class TestPdfTools:
    """Test PDF tools functionality."""

    def test_parse_page_range(self):
        from office_converter.utils.pdf_tools import parse_page_range

        assert parse_page_range("1") == [0]
        assert parse_page_range("1-3") == [0, 1, 2]
        assert parse_page_range("1,3,5") == [0, 2, 4]
        assert parse_page_range("1-3,5") == [0, 1, 2, 4]
        assert parse_page_range("") is None
        assert parse_page_range(None) is None

    def test_merge_pdfs_no_files(self):
        from office_converter.utils.pdf_tools import merge_pdfs
        result = merge_pdfs([], "/tmp/output.pdf")
        assert result is not True  # Should fail with no files (returns error string)


class TestConverters:
    """Test converter classes."""

    def test_excel_extensions(self):
        from office_converter.converters import ExcelConverter
        assert ".xlsx" in ExcelConverter.SUPPORTED_EXTENSIONS
        assert ".xls" in ExcelConverter.SUPPORTED_EXTENSIONS

    def test_word_extensions(self):
        from office_converter.converters import WordConverter
        assert ".docx" in WordConverter.SUPPORTED_EXTENSIONS
        assert ".doc" in WordConverter.SUPPORTED_EXTENSIONS

    def test_ppt_extensions(self):
        from office_converter.converters import PPTConverter
        assert ".pptx" in PPTConverter.SUPPORTED_EXTENSIONS
        assert ".ppt" in PPTConverter.SUPPORTED_EXTENSIONS
