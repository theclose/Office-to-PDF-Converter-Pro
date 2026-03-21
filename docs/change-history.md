# Change History — Office to PDF Converter Pro

## Performance Optimizations
| ID | What | File |
|----|------|------|
| B1 | COM health-check skip 30s interval | com_pool.py |
| B2 | gc.collect() 9→4 calls | excel/word/ppt.py |
| B3 | Progress throttle 100ms + log batch + animation coalesce | conversion_mixin.py |
| B5 | SQLite batch_log() + single flush() | recent_files.py |
| B6 | PDF compression skip threshold + icon skip | compression.py |
| B7 | Parallel taskkill via ThreadPoolExecutor | engine.py |

## Bug Fixes
| ID | What | File |
|----|------|------|
| F1 | Cross-thread COM cleanup removed | engine.py |
| F3 | Null COM refs instead of release_pool() | dialogs_mixin.py |
| F4 | Parallel taskkill in _on_closing() | dialogs_mixin.py |
| F6 | Log textbox capped at 2000 lines | dialogs_mixin.py |
| F7 | db.flush() before os._exit(0) | dialogs_mixin.py |
| Q1 | PPT quality bug: param was ignored | ppt.py |
| C3 | Stale HAS_PYMUPDF → get_fitz() | engine.py |
| PDF-P0 | HAS_PYMUPDF stale → all 14 PDF ops failed | core/pdf/*.py |
| PDF-P1a | delete_pages: 0-page PDF guard | pages.py |
| PDF-P1b | Bare excepts → except Exception | compression.py |
| PDF-P1c | import io top-level, dup shutil removed | security/compression |
| PDF-P1d | merge_pdfs logs warning for missing inputs | merge_split.py |

## Converter Hardening
| ID | What | File |
|----|------|------|
| W-FIX | Word: 3 fallback (Export→SaveAs2→PrintToPDF) | word.py |
| W-85/90 | Word: validation, password detect, corrupt repair | word.py |
| E-FIX | Excel: bare except fix + early abort | excel.py |
| E-85/90 | Excel: validation, pre-flight, sheet validation | excel.py |
| P-90 | PPT: 3 fallback, validation, retry, atexit | ppt.py |
| M2 | LibreOffice: input validation | libreoffice.py |
| PV | PDF output validation via PyMuPDF | base.py |

## UI/UX Improvements
| ID | What | File |
|----|------|------|
| U1 | DPI Awareness: SetProcessDpiAwareness(2) | run_pro.py |
| R1 | tk.Listbox → CTkTextbox (theme-native) | main_window_pro.py |
| R2 | CTkToolTip on all buttons | main_window_pro.py |
| R4 | Threaded folder scan + depth limit 5 | main_window_pro.py |
| R5 | Real Ctrl+V paste (CF_HDROP clipboard) | main_window_pro.py |
| U3 | Options in CTkScrollableFrame | main_window_pro.py |
| U5 | Font: Consolas → Segoe UI | main_window_pro.py |
| U6 | Clear files confirmation for >3 files | main_window_pro.py |
| U7 | Title bar: professional branding | main_window_pro.py |
| Q2 | 5-preset quality dropdown + hint text | main_window_pro.py |
| Q3 | Auto-compress integration in engine | engine.py |
| Q4 | ConversionOptions.com_quality/compress_level | engine.py |

## Architecture
| ID | What | File |
|----|------|------|
| B4 | Dead code removed (get_records_by_type) | progress_estimator.py |
| B8 | God Class → Mixin decomposition | main_window_pro → 3 files |
| SP1/SP2 | PDF/Excel Tools → OpsMixin extraction | *_ops_mixin.py |
| M1 | Deleted 6 broken generated test files | tests/ |
| M3 | Config: thread-safe save() | config.py |
| M4 | Engine: inspect.signature() replaces string compare | engine.py |
| C1/C2 | Global exception hooks (sys + threading) | run_pro.py |
| C4 | Log path → %LOCALAPPDATA%/OfficeToPDF_Pro/logs | logging_setup.py |
| C5 | .spec cleanup: removed invalid, added missing imports | OfficeToPDF_Pro.spec |
| C6 | Flush log handlers before os._exit(0) | dialogs_mixin.py |
| P2 | Engine: hasattr guard on cleanup in error path | engine.py |
