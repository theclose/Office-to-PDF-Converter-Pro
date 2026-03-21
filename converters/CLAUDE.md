# Converter Rules — Office to PDF Converter Pro
# Auto-loaded when agent works in converters/ directory.

## COM STA Model (CRITICAL)
- CoInitialize() per worker thread (STA)
- COM objects MUST stay on the thread that created them
- NEVER pass COM objects between threads
- NEVER call cleanup() from main thread

## Quality Mapping
- `ConversionOptions.com_quality` → 0=Print (300dpi), 1=Screen (96dpi)
- Excel: `ExportAsFixedFormat(Quality=com_quality)`
- Word: `OptimizeFor=wdExportOptimizeForPrint|Screen`
- PPT: `ExportAsFixedFormat(Intent=ppt_intent)` — 1=Print, 2=Screen

## Fallback Chains
- Excel: 7 methods (ExportAsFixedFormat → SaveAs16 → ... → PrintOut)
- Word: 3 methods (Export → SaveAs2 → PrintToPDF)
- PPT: 3 methods (SaveAs → ExportAsFixedFormat → PrintOut)

## Pre-flight Validation
1. File exists + size (0B/500MB reject)
2. File lock check
3. Password detection (.docx ZIP check)
4. Disk space (>= 2× input)
5. Sheet validation (Excel)

## Logging Convention
- Every conversion log MUST include: file basename, size (MB), duration (seconds)
- Example: `"Excel converted [M1]: report.xlsx (2.3MB, 1.5s)"`
