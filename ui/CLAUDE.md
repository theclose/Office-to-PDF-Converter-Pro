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

## Mixin Architecture
- `main_window_pro.py` (1308 LOC) — layout, options, file panel
- `conversion_mixin.py` (379 LOC) — start/stop, progress, toggle_inputs
- `dialogs_mixin.py` (213 LOC) — log, stats, settings, _on_closing

## Verification
- ALL UI changes → run `python run_pro.py` → verify VISUALLY
- pytest does NOT test GUI rendering
- Check both Light and Dark themes after theme-related changes

## DPI
- `SetProcessDpiAwareness(2)` in run_pro.py BEFORE any GUI imports
