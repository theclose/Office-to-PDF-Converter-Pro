# CLAUDE.md — Office to PDF Converter Pro
# Auto-generated project context for AI agents.
# Last updated: 2026-03-20

## Project Overview
**Name:** Office to PDF Converter Pro v4.x
**Author:** VNTime JSC / TungDo
**Type:** Interactive Windows Desktop App (NOT daemon/service)
**Stack:** Python 3.11+ | CustomTkinter GUI | pywin32 COM Automation | PyMuPDF

## Quick Commands
```bash
# Run app
python run_pro.py

# Run core tests (90 passed, 2 skipped baseline)
python -m pytest tests/test_com_lifecycle.py tests/test_converter_integration_v2.py tests/test_engine_threading.py tests/test_core.py tests/test_bug_fixes.py -v --tb=short

# Build EXE
pyinstaller OfficeToPDF_Pro.spec

# Lint
ruff check .
```

## Architecture (4 layers + Mixin decomposition)
```
office_converter/
├── converters/          # Layer 1: COM Automation (Office → PDF)
│   ├── base.py          #   BaseConverter ABC, Factory, thread-local COM (ensure_com_initialized)
│   ├── excel.py         #   ExcelConverter — 7 fallback export, file validation, sheet validation
│   ├── word.py          #   WordConverter — 3 fallback export, corrupt repair, macro security
│   ├── ppt.py           #   PPTConverter — 3 fallback export, file validation, move retry
│   └── libreoffice.py   #   LibreOffice headless fallback (no COM)
│
├── core/                # Layer 2: Business Logic
│   ├── engine.py        #   ConversionEngine — batch orchestration, force-stop, parallel taskkill
│   ├── excel_tools.py   #   Excel-specific utilities (28KB)
│   ├── file_tools.py    #   File manipulation tools (26KB)
│   └── pdf/             #   PDF processing submodule
│       ├── compression.py  # Image compression, skip thresholds, PIL processing
│       ├── pages.py        # Page extraction/reordering
│       ├── security.py     # Password protection, permissions
│       ├── watermark.py    # Watermark overlay
│       └── merge_split.py  # PDF merge/split
│
├── ui/                  # Layer 3: Presentation (CustomTkinter)
│   ├── main_window_pro.py   # ConverterProApp (1267 LOC) — layout, options, file panel
│   ├── conversion_mixin.py  # ConversionMixin — start/stop, progress, toggle_inputs
│   ├── dialogs_mixin.py     # DialogsMixin — log, stats, settings, _on_closing
│   ├── pdf_tools_pro.py     # PDF Tools dialog (46KB)
│   ├── excel_tools_ui.py    # Excel Tools dialog (33KB)
│   └── file_tools_ui_v2.py  # File Tools dialog (21KB)
│
├── utils/               # Layer 4: Shared Infrastructure
│   ├── com_pool.py      #   COMPool singleton — RLock, health-check skip 30s, recycle at 50
│   ├── recent_files.py  #   RecentFilesDB — SQLite WAL, batch_log(), flush()
│   ├── progress_estimator.py  # AdaptiveEstimator — O(1) running totals, JSONL
│   ├── config.py        #   Config singleton — JSON read/write
│   ├── tkdnd_wrapper.py #   TkinterDnD2 wrapper for drag-drop
│   ├── watchdog.py      #   Resource monitoring
│   └── logging_setup.py #   Centralized logging
│
├── tests/               # 167 test files, 90 core tests
│   ├── conftest.py      #   Fixtures, sys.path setup
│   ├── test_com_lifecycle.py       # COM pool, health-check, recycle
│   ├── test_engine_threading.py    # Engine batch, stop, force-stop
│   ├── test_converter_integration_v2.py  # Converter mocking
│   ├── test_core.py     # PDF tools identity
│   └── test_bug_fixes.py # Regression tests
│
├── run_pro.py           # Entry point
├── config.json          # User settings (persisted)
├── requirements.txt     # Dependencies
└── OfficeToPDF_Pro.spec # PyInstaller build spec
```

## Critical Rules (MUST follow)

### 1. COM STA Threading
- COM objects MUST be created and used on the SAME thread
- `CoInitialize()` per thread = STA (Single-Threaded Apartment)
- COMPool.get_*() is called on worker thread ONLY
- NEVER pass COM object references between threads
- NEVER call converter.cleanup() from main thread (F1 fix applied)

### 2. Tkinter Thread-Safety
- Widget operations ONLY from main thread
- Cross-thread → `self.after(0, callback)` 
- Progress updates throttled to 100ms (B3)
- _refresh_display debounced to 50ms
- Log buffer flushed every 100ms in batch

### 3. Force-Stop Contract
- `engine.stop(force=True)` → sets `_stop_requested` + `taskkill /F` parallel
- _stop_requested checked between files (NOT mid-conversion)
- _on_closing uses parallel taskkill + os._exit(0)

### 4. Converter Pre-flight Pipeline
- File exists + file size (0B reject, >500MB reject, >100MB warn)
- File lock check (`open(file, 'rb')`)
- Password detection for .docx (ZIP EncryptedPackage check)
- Disk space check (>= 2× input size)
- Sheet index validation for Excel (auto-fallback to all sheets)

### 5. Testing Rules
- ALL COM calls MUST be mocked — do NOT launch real Office processes
- Test baseline: 90 passed, 2 skipped
- Mock injection: `sys.modules['pythoncom']` + `sys.modules['win32com.client']`
- Use `conftest.py` fixtures for sys.path setup

## Coding Conventions
- Python 3.11+, PEP 8, type hints required
- Logging via `logging_setup.get_logger("ModuleName")` — no print()
- UI errors → `messagebox.showerror()` — never crash silently  
- Exception handling: `try/except` at every callback boundary
- Resource cleanup: `try/finally` for COM, files, DB connections
- Converter logs: include file size + duration in every message

## Performance Optimizations Applied
| ID | What | Where |
|----|------|-------|
| B1 | COM health-check skip (30s interval) | com_pool.py |
| B2 | gc.collect() 9→4 calls | excel.py, word.py, ppt.py |
| B3 | Progress throttle 100ms + log batch + animation coalesce | conversion_mixin.py |
| B4 | Dead code removed (get_records_by_type) | progress_estimator.py |
| B5 | SQLite batch_log() + single flush() | recent_files.py, engine.py |
| B6 | PDF compression skip threshold ↑ + icon skip | compression.py |
| B7 | Parallel taskkill via ThreadPoolExecutor | engine.py |
| B8 | God Class → Mixin decomposition | main_window_pro.py → 3 files |
| F1 | Cross-thread COM cleanup removed | engine.py |
| F3 | Null COM refs instead of release_pool() on close | dialogs_mixin.py |
| F4 | Parallel taskkill in _on_closing() | dialogs_mixin.py |
| F6 | Log textbox capped at 2000 lines | dialogs_mixin.py |
| F7 | db.flush() before os._exit(0) | dialogs_mixin.py |
| W-FIX | Word: 3 fallback methods (Export→SaveAs2→PrintToPDF) | word.py |
| W-85 | Word: file validation, password detect, macro security, atexit | word.py |
| W-90 | Word: pre-flight pipeline, corrupt doc auto-repair | word.py |
| E-FIX | Excel: bare except fix + early abort for fatal errors | excel.py |
| E-85 | Excel: file validation, metrics logging, clipboard cleanup | excel.py |
| E-90 | Excel: sheet validation, pre-flight pipeline, success tracking | excel.py |
| P-90 | PPT: 3 fallback methods, validation, retry, metrics, atexit | ppt.py |
| P2 | Engine: hasattr guard on cleanup in error path | engine.py |
| UI | toggle_inputs() — lock all inputs during conversion | conversion_mixin.py |

## Key Dependencies
| Package | Purpose | Required? |
|---------|---------|-----------|
| pywin32 ≥306 | COM automation (Excel, Word, PPT) | Yes |
| PyMuPDF ≥1.23 | PDF manipulation (`import fitz`) | Yes |
| Pillow ≥10.0 | Image processing in PDF compression | Yes |
| customtkinter ≥5.2 | Modern Tkinter GUI framework | Yes |
| tkinterdnd2 ≥0.3 | Drag-and-drop support | Optional |
| pytesseract ≥0.3.10 | OCR (requires Tesseract installed) | Optional |
| pyinstaller ≥6.0 | Build to .exe | Dev only |

## Config (config.json)
```json
{
  "language": "vi",
  "theme": "light",
  "pdf_quality": 0,       // 0=High, 1=Low, 2=Custom DPI
  "pdf_dpi": "300",
  "scan_mode": false,
  "output_folder": "",    // empty = same as source
  "recycle_threshold": 50 // COM pool recycle count
}
```
