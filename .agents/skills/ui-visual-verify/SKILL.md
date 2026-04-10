---
name: ui-visual-verify
description: |
  Visual verification workflow for CustomTkinter GUI changes in Office to PDF Converter.
  Ensures UI changes are validated by running the app, not just by passing pytest.
  Covers layout verification, theme testing, widget rendering, text cutoff checks,
  and sub-dialog verification (Excel Tools, File Tools, PDF Tools).
  Use this skill after making ANY change to files in the ui/ directory.
---

# UI Visual Verification Skill

## When to Use
- After ANY change to files in `ui/` directory
- After changing window geometry, widget sizes, or layout
- After modifying theme, colors, or fonts
- After adding/removing UI elements
- After modifying Excel Tools, File Tools, or PDF Tools dialogs

## Pre-Change Checklist
Before modifying UI code:
- [ ] Read `ui/CLAUDE.md` for layout rules
- [ ] Read `docs/gui-rules.md` for detailed constraints
- [ ] Note current values: `pack_propagate`, `width`, `geometry`

## Critical Rules (from docs/gui-rules.md)
```
right_frame: pack_propagate(False), width=468px
Window: 1100×750, minsize 1000×700
File list: CTkTextbox (NOT tk.Listbox)
Cross-thread: self.after(0, callback) ONLY
```

## Verification Steps

### Step 1: Run App
```bash
python run_pro.py
```

### Step 2: Main Window Checks
- [ ] **Text cutoff:** All labels, buttons, switches fully visible
- [ ] **Dropdown text:** Quality presets not truncated
- [ ] **Section headers:** Clearly visible and properly spaced
- [ ] **DPI entry:** Shows/hides correctly for Custom DPI preset
- [ ] **Quality hint:** Updates when changing presets
- [ ] **Password field:** Enables/disables with switch
- [ ] **File list:** Scroll works, selection highlights

### Step 3: Sub-Dialog Checks

#### Excel Tools (📊 button)
- [ ] Dialog opens without crash
- [ ] All 3 tabs visible (Chỉnh sửa, Chuyển đổi, Bảo vệ)
- [ ] Radio buttons switch operations correctly
- [ ] Options panel updates when switching operations
- [ ] File list shows sheet count and size
- [ ] Drag & drop works (if tkdnd available)

#### File Tools (📁 button)
- [ ] Dialog opens without crash
- [ ] All 3 tabs visible (Rename cơ bản, Rename nâng cao, Các chức năng khác)
- [ ] **Preview button works** (trap #21 — must pass rules param)
- [ ] **Undo button works** (trap #22 — must call undo_last_transaction)
- [ ] **Numbering options work** (trap #23 — SequenceRule at_start param)
- [ ] Disabled buttons are visually greyed out
- [ ] Old name / New name lists both populate

#### PDF Tools (🔧 button)
- [ ] Dialog opens without crash
- [ ] All operations visible in tab view
- [ ] File list accepts PDF files only

### Step 4: Theme Test
- Toggle theme switch (Light ↔ Dark)
- [ ] All widgets follow theme correctly
- [ ] No manual color overrides broken
- [ ] Sub-dialogs inherit theme
- [ ] File list CTkTextbox auto-themes

### Step 5: Resize Test
- [ ] Drag window smaller → options panel doesn't break
- [ ] Check at minimum size (1000×700)
- [ ] File list still usable

### Step 6: Automated Verification
```bash
# Verify critical code values haven't changed
python scripts/verify_claude_md.py
```
Expected checks:
- ✅ pack_propagate(False) in code
- ✅ right_frame width matches docs
- ✅ Window geometry matches docs

## Common UI Mistakes to Avoid
1. Changing `pack_propagate(False)` to `True` (trap #1)
2. Using `tk.Listbox` instead of `CTkTextbox` for themed file lists
3. Calling widget methods from worker thread (trap #5)
4. Forgetting to test both Light and Dark themes
5. Not checking text cutoff after width/font changes
6. UI calling wrong core method name after refactor (traps #21-23)
7. Placeholder buttons with no command — disable them instead
