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

## 12. CTkEntry textvariable + dynamic destroy → TclError/AttributeError
- **Bug:** Switching options in PDF Tools causes `TclError: invalid command name` or `AttributeError: 'str' object has no attribute 'get'`
- **Cause:** `_update_options_panel()` destroys widgets including CTkEntry with active textvariable write-trace. The trace callback fires on the dead widget → TclError. First fix attempt `configure(textvariable="")` corrupted `_textvariable` to string → AttributeError
- **Fix:** Use `_safe_destroy_children()` → recursively find CTkEntry, call `tv.trace_remove('write', cb_name)` to remove the trace, set `_textvariable = None`, then destroy
- **Rule:** NEVER use `configure(textvariable="")` to detach. ALWAYS use `trace_remove()` + set to `None`. NEVER destroy CTkEntry with active textvariable traces.
- **Lesson:** CustomTkinter's trace callbacks survive widget destruction. Must explicitly remove traces from StringVars before destroying.

## 13. _on_closing double-close race condition
- **Bug:** Clicking window ❌ button twice quickly triggers `_on_closing` twice → double COM cleanup → race condition
- **Cause:** No reentrance guard — `_on_closing` was not idempotent
- **Fix:** Add `_closing_in_progress` flag checked at entry. Also try `self.destroy()` before `os._exit(0)` for graceful exit.
- **Rule:** ALWAYS add reentrance guard to `_on_closing`. ALWAYS try graceful destroy before os._exit.
- **Lesson:** Window close event can fire multiple times on rapid clicks.

## 14. DPI entry accepts any string → COM crash
- **Bug:** User can type "abc" or "99999" into DPI entry → COM method receives invalid DPI → unrecoverable COM error
- **Cause:** CTkEntry had no validation — `int(var_dpi.get())` had try/except fallback to 300 but values like -100 or 99999 passed through
- **Fix:** Add `FocusOut` validator that clamps value to range 72-600, resets to 300 on non-numeric input
- **Rule:** ALWAYS validate numeric entries on FocusOut. NEVER send unvalidated user input to COM methods.
- **Lesson:** try/except around int() is not enough — must also validate the range.

## 15. Lambda closure captures wrong exception variable
- **Bug:** `_add_folder` inner thread exception handler used `e` from outer try block instead of local exception
- **Cause:** `except Exception:` without `as scan_err` → lambda captured `e` from enclosing scope (wrong exception)
- **Fix:** Use `except Exception as scan_err:` and `lambda err=scan_err:` to capture the correct variable
- **Rule:** ALWAYS name exception variables in nested try/except. ALWAYS use default argument in lambda to capture loop/scope variables.
- **Lesson:** Python closures capture variables by reference, not by value. Use default arguments to freeze values.

## 16. PyMuPDF save-to-original file fails
- **Bug:** `doc.save(output_path)` throws `ValueError: save to original must be incremental` when output_path == input_path
- **Cause:** PyMuPDF holds a file lock on the opened PDF. `doc.save()` to the SAME path requires `incremental=True`, but incremental mode doesn't support garbage collection or deflate
- **Fix:** Always save to `tempfile.mkstemp()` in same directory, then `shutil.move()` to final path after `doc.close()`
- **Rule:** NEVER `doc.save()` to the same path the doc was opened from. ALWAYS use temp-file-then-move.
- **Lesson:** Libraries that open files for reading keep locks. Save-to-original is a fundamental anti-pattern.

## 17. CTkEntry textvariable trace fires on destroyed widget
- **Bug:** Closing PDF Tools dialog triggers `AttributeError: 'str' object has no attribute 'get'` and `TclError: invalid command name`
- **Cause:** CTkEntry registers a `write` trace on its `StringVar`. When dialog is destroyed, the underlying Tcl widget is gone but the trace callback still references it. Any write to the StringVar fires the dead callback.
- **Fix:** Call `_detach_entry_traces(self)` recursively on the ENTIRE dialog tree BEFORE `self.destroy()` in `_on_close()`
- **Rule:** ALWAYS remove textvariable traces from CTkEntry widgets before destroying their parent dialog. Use recursive `_detach_entry_traces()`.
- **Lesson:** CustomTkinter doesn't auto-cleanup textvariable traces on destroy. This is a framework bug we must work around.

## 18. OCR temp file locked by subprocess
- **Bug:** `os.remove(tmp_path)` throws `PermissionError: Permission denied` on temp PNG created for OCR
- **Cause:** `pytesseract.image_to_pdf_or_hocr()` spawns a Tesseract subprocess that may still hold the file handle when `os.remove()` runs immediately after
- **Fix:** Retry `os.remove()` up to 3 times with 0.5s delay. If still locked, log warning and move on (OS temp cleanup handles it)
- **Rule:** NEVER assume a subprocess releases file locks immediately. Use retry-with-delay for temp file cleanup.
- **Lesson:** Windows holds file locks longer than Linux. Always use retry patterns for cross-process temp file cleanup.

## 19. COM proxy non-None but dead ('Object is not connected to server')
- **Bug:** `self._word.Documents.Open()` throws `-2147220995: Object is not connected to server` during batch conversion
- **Cause:** Word.exe crashed or was killed externally. The Python COM proxy `self._word` is still non-None, so `if not self._word` passes. But the underlying COM server is gone.
- **Fix:** Add `_is_word_alive()` / `_is_excel_alive()` / `_is_ppt_alive()` that probes `self._xxx.Name` (lightweight read). If it throws, set `self._xxx = None` and call `initialize()` to reconnect.
- **Rule:** NEVER trust a non-None COM proxy. ALWAYS probe with a lightweight property read before use.
- **Lesson:** COM proxies survive server crashes as zombie objects. The Python check `if obj:` returns True for dead proxies. Only a real property access reveals the truth.
