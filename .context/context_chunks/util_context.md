# UTIL Layer Context

This chunk contains 15 modules related to util.

## __init__.py
- **Path**: `utils\__init__.py`
- **Lines**: 16

## com_pool.py
- **Path**: `utils\com_pool.py`
- **Lines**: 271
- **Classes**: COMPool
- **Functions**: get_pool, release_pool
- **Purpose**: COM Connection Pool - Manages and reuses COM application instances.
Implements Singleton pattern for each Office application.

## config.py
- **Path**: `utils\config.py`
- **Lines**: 115
- **Classes**: Config
- **Purpose**: Configuration Management - Centralized settings handling.

## dnd_helpers.py
- **Path**: `utils\dnd_helpers.py`
- **Lines**: 71
- **Functions**: parse_dropped_paths
- **Purpose**: Drag & Drop Helper Utilities
Provides robust path parsing for TkinterDnD2 events with full Unicode support.

## history.py
- **Path**: `utils\history.py`
- **Lines**: 134
- **Classes**: ConversionRecord, ConversionHistory
- **Functions**: get_history
- **Purpose**: Conversion History - Track and display conversion history.

## localization.py
- **Path**: `utils\localization.py`
- **Lines**: 524
- **Functions**: set_language, get_current_language, get_text, get_language_names
- **Purpose**: Localization Module - Multi-language support.

## logging_setup.py
- **Path**: `utils\logging_setup.py`
- **Lines**: 65
- **Functions**: setup_logging, get_logger
- **Purpose**: Logging Setup - Configures application-wide logging with rotation.

## ocr.py
- **Path**: `utils\ocr.py`
- **Lines**: 368
- **Functions**: is_ocr_available, get_tesseract_languages, ocr_image, get_best_language, ocr_pdf_to_searchable, _ocr_with_pymupdf, _ocr_with_pdf2image, extract_text_from_pdf, get_ocr_status
- **Purpose**: OCR Module - Optical Character Recognition for scanned PDFs.
Uses Tesseract OCR to make scanned PDFs searchable.

Requirements:
- Tesseract OCR must be installed (https://github.com/UB-Mannheim/tesser

## parallel_converter.py
- **Path**: `utils\parallel_converter.py`
- **Lines**: 365
- **Classes**: JobStatus, ConversionJob, ConversionResult, ParallelConverter
- **Functions**: _worker_process, get_parallel_converter, shutdown_parallel_converter
- **Purpose**: Parallel Conversion System
============================
Multi-process conversion for 2-4x throughput improvement.

Each worker process has its own COM instance to avoid threading issues.
Uses multipro

## pdf_tools.py
- **Path**: `utils\pdf_tools.py`
- **Lines**: 71
- **Purpose**: PDF Tools - Utilities for PDF manipulation.
Re-exports from core.pdf_tools for backward compatibility.

DEPRECATED: Import from office_converter.core.pdf_tools instead.
- **Depends on**: office_converter.core.pdf_tools

## progress_estimator.py
- **Path**: `utils\progress_estimator.py`
- **Lines**: 466
- **Classes**: SystemProfile, SystemProfiler, ConversionRecord, ConversionLogger, AdaptiveEstimator
- **Functions**: get_system_profiler, get_conversion_logger, get_adaptive_estimator, estimate_conversion_time, log_conversion_result
- **Purpose**: Adaptive Progress Estimation System
====================================
Intelligent progress estimation using machine learning from historical data.

Components:
- SystemProfiler: Detects and records

## recent_files.py
- **Path**: `utils\recent_files.py`
- **Lines**: 173
- **Classes**: RecentFilesDB
- **Functions**: get_recent_files_db
- **Purpose**: Recent Files Database - SQLite-based storage for file history.
Extracted from main_window_pro.py for better modularity.

## tkdnd_wrapper.py
- **Path**: `utils\tkdnd_wrapper.py`
- **Lines**: 161
- **Classes**: TkinterDnD, TkDnDWrapper
- **Functions**: setup_widget_dnd
- **Purpose**: TkinterDnD2 + CustomTkinter Integration
Provides wrapper class for combining tkinterdnd2 with customtkinter.

## updater.py
- **Path**: `utils\updater.py`
- **Lines**: 269
- **Classes**: UpdateInfo, UpdateChecker
- **Functions**: show_update_dialog, check_for_updates_on_startup, _show_no_update_message
- **Purpose**: Office to PDF Converter Pro - Auto Update Checker
Version 4.0.0

Checks GitHub releases for new versions.
- **Depends on**: office_converter

## watchdog.py
- **Path**: `utils\watchdog.py`
- **Lines**: 294
- **Classes**: HealthMetrics, ConversionTracker, Watchdog
- **Functions**: get_watchdog, start_watchdog, stop_watchdog
- **Purpose**: Watchdog & Health Monitoring System
=====================================
Monitors application and worker health for 24/7 stability.

Features:
- Worker health monitoring
- Automatic worker restart on

