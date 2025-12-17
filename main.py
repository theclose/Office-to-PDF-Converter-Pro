#!/usr/bin/env python3
"""
Office Converter - Main Entry Point
Converts Office documents (Excel, Word, PowerPoint) to PDF.
"""

import os
import sys

# Add parent directory to path if running directly
package_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(package_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from office_converter.utils.logging_setup import setup_logging, get_logger
from office_converter.utils.config import Config
from office_converter.converters import ExcelConverter


def test_modules():
    """Test that all modules load correctly."""
    logger = get_logger("test")
    
    print("=" * 50)
    print("Office Converter - Module Test")
    print("=" * 50)
    
    # Test 1: Logging
    print("\n[TEST 1] Logging System...")
    logger.info("Test log message - INFO")
    logger.warning("Test log message - WARNING")
    print("  ✅ Logging works!")
    
    # Test 2: Config
    print("\n[TEST 2] Config System...")
    config = Config()
    print(f"  Language: {config.language}")
    print(f"  Theme: {config.theme}")
    print(f"  PDF Quality: {config.pdf_quality}")
    print("  ✅ Config works!")
    
    # Test 3: ExcelConverter
    print("\n[TEST 3] ExcelConverter...")
    converter = ExcelConverter()
    print(f"  Supported: {ExcelConverter.SUPPORTED_EXTENSIONS}")
    print(f"  Supports .xlsx: {ExcelConverter.supports_file('test.xlsx')}")
    print(f"  Supports .docx: {ExcelConverter.supports_file('test.docx')}")
    print("  ✅ ExcelConverter works!")
    
    # Test 4: PDF Tools
    print("\n[TEST 4] PDF Tools...")
    from office_converter.utils.pdf_tools import parse_page_range, HAS_PYMUPDF
    pages = parse_page_range("1-3, 5, 7-10")
    print(f"  Parsed '1-3, 5, 7-10': {pages}")
    print(f"  PyMuPDF available: {HAS_PYMUPDF}")
    print("  ✅ PDF Tools works!")
    
    # Test 5: Localization
    print("\n[TEST 5] Localization...")
    from office_converter.utils.localization import get_text, get_language_names
    print(f"  Languages: {list(get_language_names().keys())}")
    print(f"  'btn_convert' (vi): {get_text('btn_convert', 'vi')}")
    print(f"  'btn_convert' (en): {get_text('btn_convert', 'en')}")
    print("  ✅ Localization works!")
    
    print("\n" + "=" * 50)
    print("ALL TESTS PASSED! ✅")
    print("=" * 50)
    
    # Check log file
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    if os.path.exists(log_dir):
        log_files = os.listdir(log_dir)
        if log_files:
            print(f"\n📄 Log files created in: {log_dir}")
            for f in log_files:
                print(f"   - {f}")


if __name__ == "__main__":
    # Setup logging first
    setup_logging()
    
    # Run tests
    test_modules()
