# CLAUDE.md — Office to PDF Converter Pro v4.2.x
# Python 3.11+ | CustomTkinter | pywin32 COM | PyMuPDF
# Last updated: 2026-03-21
#
# PROGRESSIVE DISCLOSURE: This file is kept lean (< 150 lines).
# Detailed docs are in docs/ and subdirectory CLAUDE.md files.
# See: docs/architecture.md, docs/gui-rules.md, docs/converters-guide.md

## Quick Commands
```bash
python run_pro.py                    # Run app
python -m pytest tests/ -v --tb=short  # Test (baseline: 107 passed, 2 skipped)
pyinstaller OfficeToPDF_Pro.spec     # Build EXE
ruff check .                         # Lint
```

## Architecture Overview
```
converters/   → COM Automation (Excel/Word/PPT → PDF)
core/         → Engine, PDF processing, Excel/File tools
ui/           → CustomTkinter GUI, Mixins (main_window + 2 mixins)
utils/        → COMPool, Config, Logging, OCR
docs/         → Detailed documentation (progressive disclosure)
```
Full file map with LOC: see docs/architecture.md

## Critical Rules

### 1. COM STA Threading
COM objects MUST be created and used on the SAME thread.
NEVER pass COM objects between threads. NEVER call cleanup() from main thread.
Details: see converters/CLAUDE.md

### 2. Tkinter Thread-Safety
Widget operations ONLY from main thread.
Cross-thread → `self.after(0, callback)`. Progress throttled 100ms.

### 3. Force-Stop Contract
`engine.stop(force=True)` → `_stop_requested` + `taskkill /F` parallel.
`_on_closing` uses parallel taskkill + os._exit(0).

### 4. GUI Layout (CRITICAL)
- right_frame: `pack_propagate(False)` — MUST be False (enforces 468px width)
- WHY: CTkScrollableFrame shrinks parent if True → text cutoff bug
- ALL UI changes MUST be verified visually (pytest does NOT test GUI)
- Details: see docs/gui-rules.md and ui/CLAUDE.md

### 5. Quality System (5 presets)
```
0=⭐ Tối đa   → COM Print (300dpi), no compress
1=🔵 Cao      → COM Print (300dpi), light compress
2=🟢 Cân bằng  → COM Print (300dpi), medium compress
3=🟡 Nhỏ gọn   → COM Screen (96dpi), heavy compress
4=⚙️ Custom   → User DPI, no auto-compress
```
Mapping: `ConversionOptions.com_quality` + `.compress_level`
Details: see docs/converters-guide.md

### 6. Testing
- ALL COM calls MUST be mocked — NO real Office processes
- Baseline: 107 passed, 2 skipped
- Mock: `sys.modules['pythoncom']` + `sys.modules['win32com.client']`

### 7. Pre-flight Validation
File exists → size check → lock check → password detect → disk space.
Details: see docs/converters-guide.md

## Coding Conventions
- Type hints required. Logging via `logging_setup.get_logger()` — no print()
- UI errors → `messagebox.showerror()`. try/except at every callback boundary.
- Converter logs: include file size + duration in every message.
- Config: `config.set(key, val, auto_save=False)` when batching multiple sets.

## Verification Rules
- Code changes → run pytest (107 baseline)
- UI changes → run app + verify visually + THEN run pytest
- Bug fixes → add entry to docs/known-traps.md
- Config changes → verify config.json keys match docs/architecture.md

## Documentation Structure
```
CLAUDE.md              ← You are here (lean, < 150 lines)
docs/architecture.md   ← File map, LOC, dependencies, config
docs/converters-guide.md ← COM rules, quality mapping, fallback chains
docs/gui-rules.md      ← Tkinter rules, layout, thread safety
docs/known-traps.md    ← Lessons learned from real bugs (7 entries)
docs/change-history.md ← Full change log (60+ entries by category)
ui/CLAUDE.md           ← Auto-loaded for UI work
converters/CLAUDE.md   ← Auto-loaded for converter work
core/CLAUDE.md         ← Auto-loaded for engine/PDF work
```
