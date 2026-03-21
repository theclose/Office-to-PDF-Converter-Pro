# Core Rules — Office to PDF Converter Pro
# Auto-loaded when agent works in core/ directory.

## Core Modules
- `engine.py` — ConversionEngine: batch orchestration, force-stop, auto-compress
- `excel_tools.py` — Excel-specific utilities (826 LOC)
- `file_tools.py` — File manipulation tools (677 LOC)

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
- `compression.py` — 5 presets (extreme/low/medium/high/lossless) + custom (995 LOC)
- `ghostscript.py` — GS wrapper: auto-detect, hybrid pipeline, fallback (364 LOC)
- `pages.py` — Page extraction/reordering (262 LOC)
- `security.py` — Password protection (188 LOC)
- `watermark.py` — Watermark overlay (60 LOC)
- `merge_split.py` — PDF merge/split (79 LOC)
- `conversion.py` — PDF conversion utilities (186 LOC)
- Hybrid Pipeline: Ghostscript (lossy images) → PyMuPDF (lossless structure) → Smart Fallback
- Image type auto-detection: photo→JPEG progressive, diagram→PNG, B&W→skip
- Adaptive DPI: calculates needed DPI from render rect, avoids upsampling small images
- Image replacement: MUST use delete_image+insert_image (NOT update_stream — see trap #11)
- Post-process order: page extraction → password → scan mode → auto-compress

## Resource Cleanup
- `try/finally` for all COM, file handles, DB connections
- COMPool recycles at threshold=50 uses
- Health-check skipped if <30s since last
