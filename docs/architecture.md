# Architecture — Office to PDF Converter Pro v4.2.x

## Tech Stack
- **Language:** Python 3.11+
- **GUI:** CustomTkinter (CTk) + tkinterdnd2
- **COM:** pywin32 (STA model)
- **PDF:** PyMuPDF (fitz) + Pillow + Ghostscript (optional)
- **Build:** PyInstaller

## 4-Layer Architecture
```
Layer 1: converters/    → COM Automation (Office → PDF)
Layer 2: core/          → Business Logic (Engine, PDF tools, Excel tools)
Layer 3: ui/            → Presentation (CustomTkinter GUI, Mixins)
Layer 4: utils/         → Shared Infrastructure (COMPool, Config, Logging)
```

## File Map (with LOC)

### converters/ — COM Automation
| File | LOC | Purpose |
|------|-----|---------|
| base.py | 228 | BaseConverter ABC, Factory, _validate_pdf_output |
| excel.py | 512 | ExcelConverter — 7 fallback, sheet validation |
| word.py | 415 | WordConverter — 3 fallback, corrupt repair |
| ppt.py | 345 | PPTConverter — 3 fallback, quality-mapped intent |
| libreoffice.py | 208 | LibreOffice headless fallback |
| parallel_converter.py | 365 | Multi-process batch conversion |

### core/ — Business Logic
| File | LOC | Purpose |
|------|-----|---------|
| engine.py | 473 | ConversionEngine — batch, force-stop, auto-compress |
| excel_tools.py | 826 | Excel-specific utilities |
| file_tools.py | 677 | File manipulation tools |
| pdf/common.py | 34 | get_fitz(), HAS_PIL flag |
| pdf/compression.py | 1471 | Image compression pipeline (hybrid GS+PyMuPDF, image type detection) |
| pdf/ghostscript.py | 364 | Ghostscript wrapper (auto-detect, hybrid pipeline, fallback) |
| pdf/pages.py | 262 | Page extraction/reordering |
| pdf/security.py | 188 | Password protection |
| pdf/watermark.py | 60 | Watermark overlay |
| pdf/merge_split.py | 190 | PDF merge/split |
| pdf/conversion.py | 186 | PDF conversion utilities |

### ui/ — Presentation
| File | LOC | Purpose |
|------|-----|---------|
| main_window_pro.py | 1588 | ConverterProApp — layout, options, file panel |
| conversion_mixin.py | 457 | ConversionMixin — start/stop, progress |
| dialogs_mixin.py | 279 | DialogsMixin — log, stats, _on_closing |
| pdf_tools_pro.py | 983 | PDF Tools dialog |
| pdf_tools_ops_mixin.py | 361 | PDF Tools operations |
| excel_tools_ui.py | 601 | Excel Tools dialog |
| excel_tools_ops_mixin.py | 297 | Excel Tools operations |
| file_tools_ui_v2.py | 461 | File Tools dialog |
| file_tools_ui.py | 795 | File Tools dialog (legacy) |
| dialogs.py | 153 | Legacy settings dialog |

### utils/ — Infrastructure
| File | LOC | Purpose |
|------|-----|---------|
| com_pool.py | 313 | COMPool singleton — RLock, health-check, recycle |
| config.py | 119 | Config singleton — JSON, thread-safe save() |
| recent_files.py | 211 | RecentFilesDB — SQLite WAL, batch_log() |
| progress_estimator.py | 336 | AdaptiveEstimator — JSONL persistence |
| logging_setup.py | 68 | Centralized logging → %LOCALAPPDATA% |
| tkdnd_wrapper.py | 161 | TkinterDnD2 wrapper |
| watchdog.py | 234 | Resource monitoring |
| localization.py | 105 | i18n language support |
| ocr.py | 368 | OCR via pytesseract |
| updater.py | 269 | App auto-update checker |
| history.py | 134 | Conversion history tracking |
| dnd_helpers.py | 71 | Drag-and-drop helper utilities |
| pdf_tools.py | 121 | PDF tools utility functions |

## Entry Point
- `run_pro.py` — DPI awareness, exception hooks, launches ConverterProApp

## Dependencies
| Package | Purpose | Required? |
|---------|---------|-----------|
| pywin32 ≥306 | COM automation | Yes |
| PyMuPDF ≥1.23 | PDF manipulation | Yes |
| Pillow ≥10.0 | Image processing | Yes |
| customtkinter ≥5.2 | GUI framework | Yes |
| CTkToolTip | Button tooltips | Yes |
| tkinterdnd2 ≥0.3 | Drag-and-drop | Optional |
| pytesseract ≥0.3.10 | OCR | Optional |
| pyinstaller ≥6.0 | Build to .exe | Dev only |

## Config (config.json)
```json
{
  "language": "vi",
  "theme": "light",
  "pdf_quality": 0,         // 0=Tối đa, 1=Cao, 2=Cân bằng, 3=Nhỏ gọn, 4=Custom
  "auto_compress": false,   // auto-compress PDF after conversion
  "pdf_dpi": "300",         // DPI for Custom quality mode
  "scan_mode": false,       // rasterize PDF to images
  "output_folder": "",      // empty = same as source
  "last_folder": "",        // last browsed folder
  "auto_open_folder": true, // open output folder after conversion
  "recycle_threshold": 50,  // COM pool recycle count
  "page_range": "",         // page range filter
  "default_author": "",     // default PDF author metadata
  "pdf_tools_last_operation": "",
  "metadata": {             // PDF metadata settings
    "author": "",
    "title": "",
    "password_enabled": false
  }
}
```
