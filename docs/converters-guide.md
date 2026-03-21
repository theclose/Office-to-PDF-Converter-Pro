# Converters Guide — COM Rules & Quality Mapping

## COM STA Threading Model
- **CoInitialize()** must be called per worker thread (STA = Single-Threaded Apartment)
- COM objects MUST be created AND used on the SAME thread
- NEVER pass COM object references between threads
- NEVER call converter.cleanup() from the main thread (causes crash)
- COMPool.get_*() is called on worker thread ONLY

## COMPool Lifecycle
```
Worker Thread starts → CoInitialize() → COMPool.get_excel/word/ppt()
  → Converter uses COM object → Converter completes
  → COMPool tracks usage count → At threshold (50) → recycle
  → Health-check skipped if < 30s since last check
```

## Quality System (5 presets)

### Mapping Table
| Quality | Name | COM Quality | Compress Level | Use Case |
|---------|------|-------------|----------------|----------|
| 0 | ⭐ Tối đa | 0 (Print, 300dpi) | None | In ấn chất lượng cao |
| 1 | 🔵 Cao | 0 (Print, 300dpi) | "high" (light) | File nhỏ hơn, chất lượng tốt |
| 2 | 🟢 Cân bằng | 0 (Print, 300dpi) | "medium" | Cân bằng kích thước & quality |
| 3 | 🟡 Nhỏ gọn | 1 (Screen, 96dpi) | "low" (heavy) | Chia sẻ online, email |
| 4 | ⚙️ Custom | DPI-based | None | Tùy chỉnh DPI |

### Per-Converter Implementation
- **Excel:** `ExportAsFixedFormat(Quality=com_quality)` — 0=Print 300dpi, 1=Screen 96dpi
- **Word:** `OptimizeFor=wdExportOptimizeForPrint|Screen` based on com_quality
- **PPT:** `ExportAsFixedFormat(Intent=ppt_intent)` — 1=Print, 2=Screen (Q1 fix)
- **Auto-compress:** Runs in `engine._apply_post_processing()` after conversion
- **Properties:** `ConversionOptions.com_quality` and `.compress_level` handle mapping

### Fallback Chains
- **Excel:** 7 methods (ExportAsFixedFormat → SaveAs16 → SaveAs9 → ... → PrintOut)
- **Word:** 3 methods (ExportAsFixedFormat → SaveAs2 → PrintToPDF)
- **PPT:** 3 methods (SaveAs → ExportAsFixedFormat → PrintOut)

## Pre-flight Validation Pipeline
1. File exists check
2. File size: 0B reject, >500MB reject, >100MB warn
3. File lock check (`open(file, 'rb')`)
4. Password detection for .docx (ZIP EncryptedPackage)
5. Disk space check (>= 2× input size)
6. Sheet index validation for Excel (auto-fallback to all sheets)

## PDF Output Validation
- After conversion, `_validate_pdf_output()` uses PyMuPDF to open and verify the PDF
- Catches corrupt/empty PDFs before declaring success
