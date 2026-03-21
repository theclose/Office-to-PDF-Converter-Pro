# GUI Rules — Tkinter & CustomTkinter

## Critical Layout Rules

### Right Column (Options Panel)
- **Width:** 468px (enforced)
- **`pack_propagate(False)`** — MUST be False to enforce width
  - WHY: CTkScrollableFrame inside does NOT propagate parent width
  - If True → frame shrinks to content → all text gets cut off
  - This was a verified bug (R6 regression) that took 3 iterations to fix
- **Window size:** 1100×750 (min: 1000×700)

### File List Panel
- Uses **CTkTextbox** (NOT tk.Listbox)
  - Auto-follows Light/Dark theme — no manual color sync needed
  - Rounded corners, smooth scrolling
  - Click-to-select with highlight
- Font: Segoe UI (Windows native, not Consolas)

### Options Panel Structure
```
— CÀI ĐẶT CHẤT LƯỢNG —
  📂 Thư mục xuất: [label] [Đổi]
  📊 Chất lượng PDF: [dropdown 5 presets]
  (quality hint text — italic, gray)
  📐 DPI: [entry] (shown only for Custom)
  🗜️ Tự động nén PDF sau chuyển đổi [switch]
  📷 Scan Mode (chuyển PDF thành ảnh) [switch]

— BẢO MẬT —
  🔒 Mật khẩu PDF [switch] [entry]

— TÙY CHỌN EXCEL —
  📗 Sheet: [entry] VD: 1-3, 5
  📄 Trang: [entry] Chỉ xuất trang chỉ định
```

## Thread Safety
- **Widget operations:** ONLY from main thread
- **Cross-thread updates:** `self.after(0, callback)` — NEVER direct widget calls
- **Progress updates:** Throttled to 100ms (B3 optimization)
- **_refresh_display:** Debounced to 50ms
- **Log buffer:** Flushed every 100ms in batch

## DPI Awareness
- `SetProcessDpiAwareness(2)` called in `run_pro.py` BEFORE any GUI imports
- WHY: Must be set before Tkinter initializes, otherwise High-DPI displays are blurry

## Verification Rules
- **ALL UI changes MUST be verified visually** — run `python run_pro.py` and check
- pytest does NOT test GUI rendering (it tests logic only)
- After changing layout: verify text is not cut off, controls are accessible
- After changing theme logic: test both Light and Dark modes

## Tooltips
- CTkToolTip on header buttons (📊⚙️❓)
- CTkToolTip on PDF Tools, Excel Tools, Clear buttons
- Added via R2 fix

## Drag & Drop
- tkinterdnd2 for file drag-and-drop
- Recursive folder scanning with os.walk() (R4: depth limit 5, threaded)
- Ctrl+V paste: Windows clipboard (CF_HDROP + text fallback)
