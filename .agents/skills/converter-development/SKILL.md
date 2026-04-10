---
name: converter-development
description: |
  Guide for developing and modifying Office-to-PDF converters (Excel, Word, PPT).
  Covers COM STA threading model, quality mapping, fallback chains, pre-flight 
  validation, COM pool lifecycle, and testing patterns. Use this skill when adding
  new converters, modifying existing ones, or working with COM automation.
---

# Converter Development Skill

## When to Use
- Adding a new file format converter
- Modifying fallback chain logic
- Changing quality/export parameters
- Fixing COM-related bugs
- Working with COM pool lifecycle

## Architecture
```
converters/
├── base.py           → BaseConverter ABC (inherit from this)
├── excel.py          → ExcelConverter (7 fallback methods)
├── word.py           → WordConverter (3 fallback methods)
├── ppt.py            → PPTConverter (3 fallback methods)
└── libreoffice.py    → LibreOffice headless fallback

utils/
└── parallel_converter.py → Multi-process batch conversion
```

## COM STA Rules (CRITICAL — read converters/CLAUDE.md)
```python
# CORRECT: COM on worker thread
def convert(self, input_path, output_path, **kwargs):
    pythoncom.CoInitialize()  # STA on this thread
    try:
        app = win32com.client.Dispatch("Excel.Application")
        # ... use app ...
    finally:
        pythoncom.CoUninitialize()

# WRONG: COM object from different thread
# NEVER do: self.shared_app = Dispatch(...)  # then use in another thread
```

## COM Pool Lifecycle (Traps #19-20)
```python
# COMPool manages COM apartment lifetime
# NEVER call CoUninitialize when using pool (trap #20)

# In converter cleanup():
def cleanup(self):
    if self._use_pool:
        self._word = None  # Just null the ref, pool owns the apartment
    else:
        # Only uninitialize if NOT using pool
        if self._word:
            self._word.Quit()
        pythoncom.CoUninitialize()
```

### Liveness Check Pattern (Trap #19)
```python
# COM proxy can be non-None but dead
def _is_alive(self):
    try:
        _ = self._word.Name  # Actual COM call — will throw if dead
        return True
    except Exception:
        return False
```

## Quality Mapping
```python
# ConversionOptions.com_quality property
quality 0,1,2 → com_quality=0 (Print, 300dpi) 
quality 3     → com_quality=1 (Screen, 96dpi)
quality 4     → user-specified DPI

# Per-converter usage:
# Excel: ExportAsFixedFormat(Quality=com_quality)
# Word:  OptimizeFor=wdExportOptimizeForPrint|Screen
# PPT:   Intent=ppFixedFormatIntentPrint|Screen
```

## Adding a New Converter

### 1. Create converter file
```python
# converters/new_format.py
from .base import BaseConverter

class NewFormatConverter(BaseConverter):
    def convert(self, input_path, output_path, **kwargs):
        quality = kwargs.get('quality', 0)
        # ... conversion logic ...
    
    def cleanup(self):
        # Release COM objects ON THIS THREAD
        # Guard with if not self._use_pool
        pass
```

### 2. Register in Factory
```python
# converters/base.py — ConverterFactory
@staticmethod
def get_converter(file_ext):
    # Add mapping for new format
```

### 3. Add Pre-flight Validation
Every converter MUST validate:
- File exists + readable
- File size limits (0B reject, >500MB reject)
- File lock check
- Disk space (>= 2× input)

### 4. Add Fallback Chain
```python
def convert(self, input_path, output_path, **kwargs):
    methods = [self._method1, self._method2, self._method3]
    for method in methods:
        try:
            return method(input_path, output_path, **kwargs)
        except Exception as e:
            logger.warning(f"Method failed: {e}, trying next...")
    raise ConversionError("All methods failed")
```

### 5. Testing
```python
# tests/test_converter_integration_v2.py
# ALL COM calls MUST be mocked
@patch('win32com.client.Dispatch')
def test_new_converter(mock_dispatch):
    converter = NewFormatConverter()
    converter.convert("test.newformat", "test.pdf")
    mock_dispatch.assert_called()
```

## Known Traps
- PPT quality param was silently ignored (trap #3)
- Never cache module availability in boolean (trap #2)
- COM cleanup from wrong thread crashes (trap #5)
- COM proxy non-None but dead — use liveness probe (trap #19)
- CoUninitialize kills ALL pooled COM on thread (trap #20)

## Reference Files
- `converters/CLAUDE.md` — COM rules summary
- `docs/converters-guide.md` — Full quality mapping + fallback chains
- `docs/known-traps.md` — Bug patterns to avoid (23 entries)
