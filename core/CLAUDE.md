# Core Rules — Office to PDF Converter Pro
# Auto-loaded when agent works in core/ directory.

## ConversionEngine (engine.py)
- Batch orchestration: file queue → worker threads → callbacks
- `_stop_requested` checked between files (NOT mid-conversion)
- Force-stop: `taskkill /F` via ThreadPoolExecutor
- Auto-compress: runs in `_apply_post_processing()` after conversion

## ConversionOptions
```python
quality: int = 0       # 0=max, 1=high, 2=balanced, 3=compact, 4=custom
quality_dpi: int = 300 # only for quality=4
auto_compress: bool    # auto-compress after conversion
scan_mode: bool        # rasterize PDF to images
```
- `.com_quality` property → 0 (Print) or 1 (Screen)
- `.compress_level` property → "high"/"medium"/"low" or None

## PDF Processing (core/pdf/)
- Always use `get_fitz()` for PyMuPDF — NEVER cache in boolean
- compression.py: 3 levels (high=light, medium, low=heavy)
- Post-process order: page extraction → password → scan mode → auto-compress

## Resource Cleanup
- `try/finally` for all COM, file handles, DB connections
- COMPool recycles at threshold=50 uses
- Health-check skipped if <30s since last
