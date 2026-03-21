# Audit Manifest — Danh mục PHẢI audit khi yêu cầu "audit full app"
# 
# Cách dùng:
# 1. AI đọc file này TRƯỚC khi bắt đầu audit
# 2. Đánh dấu [x] khi đã đọc + phân tích file đó
# 3. verify_claude_md.py Check 17 sẽ parse file này để kiểm tra coverage
#
# Format: - [ ] path/to/file.py (LOC) — Mô tả, risk keywords
# Tier 1 = PHẢI đọc line-by-line | Tier 2 = PHẢI scan | Tier 3 = đọc nếu liên quan

## Tier 1 — Critical (user-facing, high-risk, complex logic)
<!-- audit_tier: 1 -->
- [ ] converters/excel.py — 7 fallback methods, COM race, _safe_export path bug
- [ ] converters/word.py — 3 fallback methods, double-cleanup, COM lifecycle
- [ ] converters/ppt.py — 3 fallback methods, quality-mapped intent
- [ ] core/engine.py — Batch orchestration, force-stop, temp cleanup, threading
- [ ] core/pdf/compression.py — Hybrid pipeline GS+PyMuPDF, image detection, SSIM
- [ ] core/pdf/ghostscript.py — Subprocess timeout, zombie prevention, auto-detect
- [ ] core/pdf/merge_split.py — File handle lifecycle, fitz.open/close patterns
- [ ] core/pdf/security.py — Password protection, rasterize, memory management
- [ ] ui/pdf_tools_pro.py — PDF Tools dialog, i18n violations, threading
- [ ] ui/pdf_tools_ops_mixin.py — PDF operations, merge threading, batch processing
- [ ] ui/conversion_mixin.py — Progress callbacks, time display, threading safety
- [ ] utils/com_pool.py — COM singleton, RLock, idle timeout, cross-thread risks

## Tier 2 — Important (infrastructure, medium-risk)
<!-- audit_tier: 2 -->
- [ ] converters/base.py — BaseConverter ABC, factory, PDF validation
- [ ] converters/libreoffice.py — LibreOffice headless fallback
- [ ] core/pdf/conversion.py — pdf_to_images, pdf_to_single_image, memory
- [ ] core/pdf/watermark.py — Text width calculation, font handling
- [ ] core/pdf/pages.py — Page range parsing, extract/delete/reorder
- [ ] core/pdf/common.py — get_fitz(), HAS_PIL, lazy imports
- [ ] utils/config.py — Singleton, atomic write, thread-safe save
- [ ] utils/ocr.py — pytesseract integration, language detection
- [ ] ui/main_window_pro.py — Layout, options panel, file panel (1500+ LOC)
- [ ] ui/dialogs_mixin.py — Log panel, stats, _on_closing lifecycle

## Tier 3 — Stable (low-risk, scan-only)
<!-- audit_tier: 3 -->
- [ ] utils/parallel_converter.py — Multi-process batch
- [ ] core/excel_tools.py — Excel-specific utilities
- [ ] core/file_tools.py — File manipulation tools
- [ ] utils/logging_setup.py — Centralized logging
- [ ] utils/localization.py — i18n language support
- [ ] utils/recent_files.py — SQLite WAL history
- [ ] utils/progress_estimator.py — Adaptive time estimation
- [ ] utils/watchdog.py — Resource monitoring
- [ ] utils/updater.py — App auto-update
- [ ] utils/history.py — Conversion history tracking
- [ ] ui/excel_tools_ui.py — Excel Tools dialog
- [ ] ui/excel_tools_ops_mixin.py — Excel Tools operations
- [ ] ui/file_tools_ui_v2.py — File Tools dialog
