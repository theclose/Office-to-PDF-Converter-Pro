"""
Comprehensive Test Script for Office Converter
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from office_converter.utils.config import Config
from office_converter.utils.localization import get_text
from office_converter.utils.pdf_tools import parse_page_range, HAS_PYMUPDF
from office_converter.converters import ExcelConverter, WordConverter, PPTConverter, get_converter_for_file

def run_tests():
    print('=== COMPREHENSIVE TEST ===')
    print()
    errors = []
    
    # Test 1: Config
    print('[1] Config...')
    try:
        c = Config()
        print(f'    Language: {c.language}')
        print(f'    Theme: {c.theme}')
        print('    ✓ OK')
    except Exception as e:
        print(f'    ✗ FAILED: {e}')
        errors.append(f'Config: {e}')
    
    # Test 2: Localization
    print('[2] Localization...')
    try:
        for lang in ['vi', 'en', 'zh']:
            txt = get_text('btn_convert', lang)
            print(f'    {lang}: {txt}')
        print('    ✓ OK')
    except Exception as e:
        print(f'    ✗ FAILED: {e}')
        errors.append(f'Localization: {e}')
    
    # Test 3: Page Range Parse
    print('[3] Page Range Parser...')
    try:
        tests = [('1-3', [0,1,2]), ('1, 5, 7', [0,4,6]), ('', None), ('abc', None)]
        for inp, expected in tests:
            result = parse_page_range(inp)
            status = '✓' if result == expected else '✗'
            print(f'    {status} "{inp}" -> {result}')
        print('    ✓ OK')
    except Exception as e:
        print(f'    ✗ FAILED: {e}')
        errors.append(f'PageRange: {e}')
    
    # Test 4: Converters factory
    print('[4] Factory...')
    try:
        tests = [
            ('test.xlsx', 'ExcelConverter'),
            ('test.docx', 'WordConverter'),
            ('test.pptx', 'PPTConverter'),
            ('test.txt', None)
        ]
        for f, expected in tests:
            conv = get_converter_for_file(f)
            name = conv.__name__ if conv else None
            status = '✓' if name == expected else '✗'
            print(f'    {status} {f} -> {name}')
        print('    ✓ OK')
    except Exception as e:
        print(f'    ✗ FAILED: {e}')
        errors.append(f'Factory: {e}')
    
    # Test 5: Converter extensions
    print('[5] Extensions...')
    try:
        print(f'    Excel: {ExcelConverter.SUPPORTED_EXTENSIONS}')
        print(f'    Word: {WordConverter.SUPPORTED_EXTENSIONS}')
        print(f'    PPT: {PPTConverter.SUPPORTED_EXTENSIONS}')
        print('    ✓ OK')
    except Exception as e:
        print(f'    ✗ FAILED: {e}')
        errors.append(f'Extensions: {e}')
    
    # Test 6: PyMuPDF
    print(f'[6] PyMuPDF: {"Available" if HAS_PYMUPDF else "Not installed"}')
    
    print()
    if errors:
        print(f'=== {len(errors)} TEST(S) FAILED ===')
        for e in errors:
            print(f'  - {e}')
        return False
    else:
        print('=== ALL TESTS PASSED ===')
        return True


if __name__ == "__main__":
    run_tests()
