# UI Rules — Office to PDF Converter Pro
# Auto-loaded when agent works in ui/ directory.

## Layout Rules
- **right_frame:** width=468px, `pack_propagate(False)` — DO NOT CHANGE
  - WHY: CTkScrollableFrame shrinks parent if True → text cutoff bug
- **Window:** 1100×750, min 1000×700
- **File list:** CTkTextbox (NOT tk.Listbox) — auto-follows theme
- **Options panel:** 3 sections separated by headers (Chất lượng / Bảo mật / Excel)
- **Quality dropdown:** CTkComboBox, 5 presets, hint text updates on change

## Thread Safety
- Widget ops ONLY from main thread
- Cross-thread → `self.after(0, callback)`
- Progress throttle: 100ms
- Log buffer flush: 100ms batch

## UI Modules
- `main_window_pro.py` (1265 LOC) — layout, options, DnD
- `file_panel.py` (340 LOC) — FileListPanel component (extracted from main_window)
- `conversion_mixin.py` (457 LOC) — start/stop, progress, toggle_inputs
- `dialogs_mixin.py` (279 LOC) — log, stats, settings, _on_closing
- `pdf_tools_pro.py` (849 LOC) — PDF Tools dialog (compress, merge, split, etc.)
- `pdf_tools_ops_mixin.py` (311 LOC) — PDF Tools operations (threading, callbacks)
- `excel_tools_ui.py` (601 LOC) — Excel Tools dialog
- `excel_tools_ops_mixin.py` (297 LOC) — Excel Tools operations
- `file_tools_ui.py` (795 LOC) — File Tools dialog (legacy)
- `file_tools_ui_v2.py` (461 LOC) — File Tools dialog (v2)

## Verification
- ALL UI changes → run `python run_pro.py` → verify VISUALLY
- pytest does NOT test GUI rendering
- Check both Light and Dark themes after theme-related changes

## DPI
- `SetProcessDpiAwareness(2)` in run_pro.py BEFORE any GUI imports
