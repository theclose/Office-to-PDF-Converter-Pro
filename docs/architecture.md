# Architecture — Office to PDF Converter Pro v4.2.x
# Last updated: 2026-04-02

## Tech Stack
- **Language:** Python 3.11+
- **GUI:** CustomTkinter (CTk) + tkinterdnd2
- **COM:** pywin32 (STA model)
- **PDF:** PyMuPDF (fitz) + Pillow + Ghostscript (optional)
- **Build:** PyInstaller

## 4-Layer Architecture
```
Layer 1: converters/    → COM Automation (Office → PDF)
Layer 2: core/          → Business Logic (Engine, PDF tools, Excel tools, File tools)
Layer 3: ui/            → Presentation (CustomTkinter GUI, Mixins)
Layer 4: utils/         → Shared Infrastructure (COMPool, Config, Logging, i18n)
```

## File Map (with LOC)

### converters/ — COM Automation
| File | LOC | Purpose |
|------|-----|---------|
| base.py | 232 | BaseConverter ABC, Factory, _validate_pdf_output |
| excel.py | 537 | ExcelConverter — 7 fallback, sheet validation |
| word.py | 445 | WordConverter — 3 fallback, corrupt repair |
| ppt.py | 378 | PPTConverter — 3 fallback, quality-mapped intent |
| libreoffice.py | 215 | LibreOffice headless fallback |

### core/ — Business Logic
| File | LOC | Purpose |
|------|-----|---------|
| engine.py | 476 | ConversionEngine — batch, force-stop, auto-compress |
| excel_tools.py | 825 | Excel-specific utilities |
| file_tools.py | 678 | Rename rules, duplicate finder, attributes manager |
| pdf_tools.py | 40 | PDF tool orchestration (bridge to core/pdf/) |
| pdf/common.py | 34 | get_fitz(), HAS_PIL flag |
| pdf/compression.py | 1498 | Image compression pipeline (hybrid GS+PyMuPDF, image type detection) |
| pdf/ghostscript.py | 374 | Ghostscript wrapper (auto-detect, hybrid pipeline, fallback) |
| pdf/pages.py | 262 | Page extraction/reordering |
| pdf/security.py | 200 | Password protection |
| pdf/watermark.py | 71 | Watermark overlay |
| pdf/merge_split.py | 221 | PDF merge/split |
| pdf/conversion.py | 221 | PDF ↔ Image conversion |

### ui/ — Presentation
| File | LOC | Purpose |
|------|-----|---------|
| main_window_pro.py | 1436 | ConverterProApp — layout, options, DnD |
| file_panel.py | 363 | FileListPanel — file list, drag&drop, selection |
| collapsible_section.py | 106 | CollapsibleSection — accordion widget for options |
| conversion_mixin.py | 517 | ConversionMixin — start/stop, progress |
| dialogs_mixin.py | 290 | DialogsMixin — log, stats, _on_closing |
| pdf_tools_pro.py | 986 | PDF Tools dialog |
| pdf_tools_ops_mixin.py | 372 | PDF Tools operations |
| excel_tools_ui.py | 600 | Excel Tools dialog |
| excel_tools_ops_mixin.py | 297 | Excel Tools operations |
| file_tools_ui_v2.py | 460 | File Tools dialog (current) |
| file_tools_ui.py | 795 | File Tools dialog (legacy) |
| dialogs.py | 153 | Legacy settings dialog |

### utils/ — Infrastructure
| File | LOC | Purpose |
|------|-----|---------|
| com_pool.py | 384 | COMPool singleton — RLock, health-check, zombie kill, recycle |
| config.py | 144 | Config singleton — JSON, thread-safe save() |
| parallel_converter.py | 363 | Multi-process batch conversion |
| recent_files.py | 211 | RecentFilesDB — SQLite WAL, batch_log() |
| progress_estimator.py | 354 | AdaptiveEstimator — JSONL persistence |
| logging_setup.py | 68 | Centralized logging → %LOCALAPPDATA% |
| localization.py | 104 | i18n language support (5 languages) |
| tkdnd_wrapper.py | 161 | TkinterDnD2 wrapper |
| watchdog.py | 233 | Resource monitoring |
| ocr.py | 407 | OCR via pytesseract |
| updater.py | 269 | App auto-update checker |
| history.py | 137 | Conversion history tracking |
| dnd_helpers.py | 71 | Drag-and-drop helper utilities |
| pdf_tools.py | 121 | PDF tools utility functions |

### locales/ — Internationalization
| File | Language |
|------|----------|
| vi.json | Tiếng Việt (default) |
| en.json | English |
| zh.json | 中文 |
| ja.json | 日本語 |
| ko.json | 한국어 |

### tests/ — Test Suite (baseline: 188+ passed, 4 skipped)
| File | Coverage | Purpose |
|------|----------|---------|
| test_integration_library.py | ~12 tests | PDF compression, merge/split |
| test_integration_ui_lifecycle.py | ~7 tests | Dialog lifecycle, widget cleanup |
| test_integration_converter.py | ~8 tests | Real COM conversion (requires Office) |
| test_stress_file_handling.py | ~12 tests | Concurrency, temp cleanup |
| test_split_features.py | ~6 tests | PDF page operations |
| test_compression_features.py | ~8 tests | All compression modes |
| test_core.py | ~30 | Engine logic, conversion options |
| test_bug_fixes.py | ~10 | Regression tests |
| test_com_lifecycle.py | ~10 | COM pool/lifecycle tests |
| test_engine_threading.py | ~10 | Thread safety |
| test_fallback_chain.py | ~15 | Converter fallback chains |
| test_file_tools.py | ~6 tests | Rename rules, duplicates, undo |
| test_file_tools_quality.py | ~10 | File tools edge cases |
| test_converter_integration_v2.py | ~20 | Converter integration |
| conftest.py | — | Shared fixtures (COM mocks) |
| conftest_integration.py | — | Integration fixtures (real files) |

### scripts/ — Dev Tools
| File | Purpose |
|------|---------|
| verify_claude_md.py | CLAUDE.md verification (18 checks) |
| pre-commit | Git pre-commit hook |
| install_hooks.py | Install git hooks |

### Build
| File | Purpose |
|------|---------|
| OfficeToPDF_Pro.spec | PyInstaller spec — single EXE (~44 MB) |
| run_pro.py | Entry point — DPI awareness, exception hooks |

## Entry Point
- `run_pro.py` → DPI awareness → exception hooks → `ConverterProApp`
- Build: `pyinstaller OfficeToPDF_Pro.spec --clean` → `dist/OfficeToPDF_Pro.exe`

## Dependencies
| Package | Purpose | Required? |
|---------|---------|-----------|
| pywin32 ≥306 | COM automation | Yes |
| PyMuPDF ≥1.23 | PDF manipulation | Yes |
| Pillow ≥10.0 | Image processing | Yes |
| customtkinter ≥5.2 | GUI framework | Yes |
| CTkToolTip | Button tooltips | Yes |
| openpyxl | Excel read/write | Yes |
| tkinterdnd2 ≥0.3 | Drag-and-drop | Optional |
| windnd | Alternative DnD | Optional |
| pytesseract ≥0.3.10 | OCR | Optional |
| Ghostscript | PDF compression | Optional |
| pyinstaller ≥6.0 | Build to .exe | Dev only |

## Config (config.json)

### DEFAULT_CONFIG (code defaults — 8 keys)
```json
{
  "language": "vi",
  "theme": "light",
  "pdf_quality": 0,
  "auto_compress": false,
  "scan_mode": false,
  "output_folder": "",
  "last_folder": "",
  "recent_files": [],
  "metadata": {
    "author": "",
    "title": "",
    "password_enabled": false
  }
}
```

### Runtime keys (set by UI, not in DEFAULT_CONFIG)
| Key | Set by | Description |
|-----|--------|-------------|
| `auto_open_folder` | UI checkbox | Open output folder after conversion |
| `pdf_dpi` | Custom quality mode | DPI value (string) |
| `recycle_threshold` | Config dialog | COM pool recycle count |
| `page_range` | UI input | Page range filter |
| `default_author` | UI input | Default PDF author metadata |
| `pdf_tools_last_operation` | PDF Tools tab | Last used operation |

### Quality Presets
```
0 = ⭐ Tối đa    → COM Print (300dpi), no compress
1 = 🔵 Cao       → COM Print (300dpi), light compress
2 = 🟢 Cân bằng  → COM Print (300dpi), medium compress
3 = 🟡 Nhỏ gọn   → COM Screen (96dpi), heavy compress
4 = ⚙️ Custom    → User DPI, no auto-compress
```
