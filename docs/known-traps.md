# Known Traps — Lessons Learned from Bugs

> Each entry records a real bug, WHY it happened, and HOW to avoid it.

## 1. pack_propagate(True) breaks fixed-width frames
- **Bug:** Options panel text was cut off despite width=468px being set
- **Cause:** `pack_propagate(True)` lets CTkScrollableFrame content shrink the parent frame
- **Fix:** Use `pack_propagate(False)` for any frame with enforced width
- **Rule:** NEVER change pack_propagate(False) to True on the right_frame
- **Lesson:** "Responsive" doesn't always mean True. Fixed panels need False.

## 2. HAS_PYMUPDF boolean was stale
- **Bug:** All 14 PDF operations silently failed (compression, merge, split, etc.)
- **Cause:** `HAS_PYMUPDF` was imported once at module load → stale if fitz loaded later
- **Fix:** Always use `get_fitz()` for live runtime check
- **Rule:** Never cache module availability in a boolean. Use lazy function calls.

## 3. PPT quality param silently ignored
- **Bug:** User selected "Nhỏ gọn" but PPT still exported at full quality
- **Cause:** `quality` param was passed to `convert()` but never used in `SaveAs()` or `ExportAsFixedFormat()`
- **Fix:** Map `quality 0→Intent=Print`, `quality 1→Intent=Screen` via ppt_intent variable
- **Rule:** When adding a new param, verify it's actually USED in the implementation.

## 4. pytest does NOT test GUI rendering
- **Bug:** All 107 tests passed but UI was visually broken (text cutoff)
- **Cause:** Unit tests mock COM and test logic, not pixel rendering
- **Fix:** Visual verification is MANDATORY for UI changes — run app and check
- **Rule:** After any UI change: run app → verify visually → THEN run pytest

## 5. COM cleanup from wrong thread crashes
- **Bug:** App crashed when closing during conversion
- **Cause:** `converter.cleanup()` was called from main thread, but COM objects live on worker thread
- **Fix:** Null COM refs instead of cleanup; use parallel taskkill on close
- **Rule:** Never access/release COM objects from a different thread than where they were created.

## 6. Config.set() auto-saves by default
- **Bug:** Performance issue when updating multiple config keys
- **Cause:** Each `set()` call triggers a disk write (`json.dump`)
- **Fix:** Use `config.set(key, value, auto_save=False)` + explicit `config.save()` at the end
- **Rule:** When setting multiple config values, batch them with auto_save=False.

## 7. Self-reporting CLAUDE.md bias
- **Bug:** R6 was documented as `pack_propagate(True)` (a "fix") but it was actually a regression
- **Cause:** Agent self-reported its own changes without external verification
- **Fix:** CLAUDE.md updates must include WHY, and UI changes need visual proof
- **Rule:** Never trust CLAUDE.md entries without checking the actual code.

## 8. Unprotected UI callbacks crash on exception
- **Bug:** Event-bound callbacks (e.g. _select_all, _delete_selected) would crash the app on any unexpected error
- **Cause:** Tkinter swallows some exceptions but not all — unhandled errors propagate and crash
- **Fix:** Wrap all event-bound callbacks in try/except with logger.error
- **Rule:** Every callback bound to a UI event (command=, .bind, trace_add) MUST have try/except

## 9. Thread-unsafe utils modules under concurrent access
- **Bug:** `history.py` and `progress_estimator.py` had no thread locks despite being called from worker threads
- **Cause:** Initial implementation assumed single-threaded access, but engine runs conversions on threads
- **Fix:** Added `threading.Lock()` to both classes with `with self._lock:` around write operations
- **Rule:** Any module accessed from both main thread and worker threads MUST use threading.Lock()

## 10. self.destroy() without cancelling after() callbacks
- **Bug:** Changing language triggered `TclError: application has been destroyed` cascade crash
- **Cause:** `_change_language` called `self.destroy()` but `_refresh_job`, `_log_flush_job`, and `_update_time_display` timers were still scheduled — they fired on the destroyed window
- **Fix:** Added `_cancel_all_after_jobs()` helper that cancels all stored job IDs and sets `_closing=True` flag. Use `os._exit(0)` instead of `self.destroy()`
- **Rule:** ALWAYS call `_cancel_all_after_jobs()` before any `self.destroy()` or `os._exit()` on the main window. Modal dialogs (pdf_tools, excel_tools) are safe — they have no recurring after() callbacks.
- **Audit lesson:** Static analysis cannot detect Tkinter lifecycle bugs. MUST run app and test close/language change flows.

## 11. update_stream corrupts PDF images (CRITICAL)
- **Bug:** All compressed PDF pages rendered as completely black (quality = 0)
- **Cause:** `doc.update_stream(xref, jpeg_bytes)` replaces raw stream data but does NOT update xref metadata (Filter, Width, Height, ColorSpace, BitsPerComponent). When original image used FlateDecode but new data is JPEG (DCTDecode), the metadata mismatch causes viewer to misinterpret the stream → black/garbled output
- **Fix:** Use `page.delete_image(xref)` + `page.insert_image(rect, stream=compressed)` which correctly creates new xref with matching metadata. Use `replaced_xrefs` set to avoid processing same xref twice
- **Rule:** NEVER use `doc.update_stream()` for image replacement unless you also update ALL xref dictionary keys (Filter, Width, Height, ColorSpace, BitsPerComponent, DecodeParms). The safe method is always delete_image + insert_image.
- **Lesson:** "In-place" replacement sounds efficient but PDF xrefs have coupled metadata. Changing the stream without the metadata = silent corruption.
