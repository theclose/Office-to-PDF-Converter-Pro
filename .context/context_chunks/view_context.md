# VIEW Layer Context

This chunk contains 10 modules related to view.

## __init__.py
- **Path**: `ui\__init__.py`
- **Lines**: 4

## dialogs.py
- **Path**: `ui\dialogs.py`
- **Lines**: 153
- **Classes**: SettingsDialog
- **Functions**: show_settings
- **Purpose**: Settings Dialog - Popup for application settings.
- **Depends on**: office_converter.utils.config, office_converter.utils.localization

## excel_tools_ui.py
- **Path**: `ui\excel_tools_ui.py`
- **Lines**: 867
- **Classes**: ExcelToolsDialog
- **Purpose**: Excel Tools Dialog - Modern CustomTkinter interface for Excel operations.

Features:
- Split Excel: Export each sheet as separate file
- Merge Excel: Combine multiple files into one
- Drag & drop supp
- **Depends on**: office_converter.core.excel_tools, office_converter.utils.config, office_converter.utils.tkdnd_wrapper, office_converter.utils.dnd_helpers

## file_tools_ui.py
- **Path**: `ui\file_tools_ui.py`
- **Lines**: 797
- **Classes**: DuplicateResultWidget, RuleWidget, FileToolsDialog
- **Purpose**: UI for File Tools (Rename, etc).
- **Depends on**: office_converter.core.file_tools, office_converter.utils.tkdnd_wrapper

## file_tools_ui_v2.py
- **Path**: `ui\file_tools_ui_v2.py`
- **Lines**: 461
- **Classes**: FileToolsDialogV2
- **Purpose**: File Tools UI V2 - 3 Tab Vietnamese Interface
Based on user reference design with:
- Tab 1: Rename cơ bản (Basic Rename)
- Tab 2: Rename nâng cao (Advanced Rename)
- Tab 3: Các chức năng khác (Other F
- **Depends on**: office_converter.core.file_tools

## main_window.py
- **Path**: `ui\main_window.py`
- **Lines**: 1425
- **Classes**: ConverterApp
- **Functions**: main
- **Purpose**: Office Converter - Complete UI
Full-featured interface for converting Office documents to PDF.
Supports: Excel, Word, PowerPoint
- **Depends on**: office_converter.utils.logging_setup, office_converter.utils.config, office_converter.utils.localization, office_converter.utils.pdf_tools, office_converter.utils.history

## main_window_ctk.py
- **Path**: `ui\main_window_ctk.py`
- **Lines**: 977
- **Classes**: AnimatedButton, FileTypeIndicator, ModernConverterApp
- **Functions**: main
- **Purpose**: Office Converter - Modern UI with CustomTkinter
Version 3.1.0 - Enhanced UX with animations and context-aware options
Phase 2 + Phase 3: Collapsible panels, context-aware options, animations, microint
- **Depends on**: office_converter.utils.logging_setup, office_converter.utils.config, office_converter.utils.pdf_tools, office_converter.utils.com_pool, office_converter.utils.history

## main_window_pro.py
- **Path**: `ui\main_window_pro.py`
- **Lines**: 2134
- **Classes**: FileType, ConversionFile, ConversionOptions, ConversionEngine, FileListPanel, ConverterProApp
- **Functions**: main
- **Purpose**: Office Converter Pro - Refactored Architecture (FIXED)
Version 4.0.1 - Professional Grade with Preview, DnD, Recent Files

HOTFIX CHANGES:
- Fixed fitz import (moved to global scope with fallback)
- A
- **Depends on**: office_converter.utils.logging_setup, office_converter.utils.config, office_converter.utils.com_pool, office_converter.utils.pdf_tools, office_converter.converters

## pdf_tools_dialog.py
- **Path**: `ui\pdf_tools_dialog.py`
- **Lines**: 595
- **Classes**: PDFToolsDialog
- **Functions**: show_pdf_tools_dialog
- **Purpose**: PDF Tools Dialog - Unified interface for all PDF operations
Supports batch processing with progress tracking
Compact layout to show all controls without scrolling
- **Depends on**: office_converter.core, office_converter.utils.config

## pdf_tools_pro.py
- **Path**: `ui\pdf_tools_pro.py`
- **Lines**: 997
- **Classes**: PDFToolsDialogPro
- **Functions**: show_pdf_tools_pro
- **Purpose**: PDF Tools Dialog Pro - Modern CustomTkinter interface for PDF operations
Professional UI with dark theme, smooth animations, and batch processing
- **Depends on**: office_converter.core, office_converter.utils.config, office_converter.utils.tkdnd_wrapper, office_converter.utils.dnd_helpers

