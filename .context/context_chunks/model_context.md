# MODEL Layer Context

This chunk contains 3 modules related to model.

## excel_tools.py
- **Path**: `core\excel_tools.py`
- **Lines**: 826
- **Functions**: split_excel, merge_excel, _merge_as_sheets, _merge_as_rows, _copy_sheet_data, _sanitize_filename, _make_unique_name, get_sheet_names, get_sheet_info, excel_to_csv (+4 more)
- **Purpose**: Excel Tools - Core operations for Excel file manipulation.

Functions:
- split_excel: Export each sheet as separate Excel file
- merge_excel: Combine multiple Excel files into one

Dependencies:
- ope

## file_tools.py
- **Path**: `core\file_tools.py`
- **Lines**: 640
- **Classes**: RenamePreview, RenameRule, CaseRule, ReplaceRule, RemoveAccentsRule, TrimRule, AddStringRule, SequenceRule, ExtensionRule, DuplicateGroup, EmptyFolderCleaner, AttributeManager, DuplicateFinder, Transaction, TransactionLog, FileToolsEngine
- **Functions**: remove_vietnamese_accents
- **Purpose**: Core logic for File Tools (Rename, Manage).
Implements Command Pattern for rename rules.

## pdf_tools.py
- **Path**: `core\pdf_tools.py`
- **Lines**: 933
- **Functions**: merge_pdfs, split_pdf, protect_pdf, post_process_pdf, _apply_scan_effects, rasterize_pdf, compress_pdf, add_watermark, pdf_to_images, images_to_pdf (+7 more)
- **Purpose**: PDF Tools Module - Professional PDF Compression, Watermark, PDF↔Images
Based on PyMuPDF best practices from official documentation.

