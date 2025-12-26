# OTHER Layer Context

This chunk contains 14 modules related to other.

## __init__.py
- **Path**: `__init__.py`
- **Lines**: 5

## build_exe.py
- **Path**: `build_exe.py`
- **Lines**: 352
- **Functions**: clean, create_version_info, get_hidden_imports, get_excludes, get_data_files, build, main
- **Purpose**: Office to PDF Converter Pro - Build Script
Version 4.0.7 - Optimized Build

Usage:
    python build_exe.py          # Build .exe
    python build_exe.py --clean  # Clean build files

## build_script.py
- **Path**: `build_script.py`
- **Lines**: 129
- **Functions**: print_step, run_command, main
- **Purpose**: Build script for Office to PDF Converter Pro EXE
Automates the entire build process with optimization

## deploy_automation.py
- **Path**: `deploy_automation.py`
- **Lines**: 166
- **Functions**: run_cmd, main
- **Purpose**: Automated Deployment Script for Office Converter Pro v4.1.6
Safely automates deployment steps with user confirmation

## deploy_simple.py
- **Path**: `deploy_simple.py`
- **Lines**: 92
- **Purpose**: Simple Deployment Automation for Office Converter Pro v4.1.7
Windows PowerShell compatible version

## main.py
- **Path**: `main.py`
- **Lines**: 86
- **Functions**: test_modules
- **Purpose**: Office Converter - Main Entry Point
Converts Office documents (Excel, Word, PowerPoint) to PDF.
- **Depends on**: office_converter.utils.logging_setup, office_converter.utils.config, office_converter.converters

## merge_project.py
- **Path**: `merge_project.py`
- **Lines**: 292
- **Classes**: ProjectMerger
- **Functions**: main
- **Purpose**: RetroAuto v2 - Project Context Merger (Advanced Version)

Gộp toàn bộ source code của dự án vào một file văn bản duy nhất.
Tối ưu hóa cho việc chia sẻ context với LLM (ChatGPT, Claude, Gemini).

Featu

## run_grid.py
- **Path**: `run_grid.py`
- **Lines**: 131
- **Functions**: main
- **Purpose**: Autonomous Conversion Grid - Production Entry Point

This is the new, hardened entry point using the grid architecture.

CRITICAL: Shim layer is installed FIRST to neutralize legacy UI.

Usage:
    py

## run_pro.py
- **Path**: `run_pro.py`
- **Lines**: 37
- **Purpose**: Office to PDF Converter Pro - Entry Point (LEGACY)

⚠️ DEPRECATED: This entry point uses the legacy monolithic UI.
   Please use run_reactor.py for the modern event-driven UI:
   
   python run_reacto
- **Depends on**: office_converter.ui.main_window_pro

## run_reactor.py
- **Path**: `run_reactor.py`
- **Lines**: 35
- **Purpose**: Office Converter Reactor UI - Entry Point
=========================================
Launches the modern, event-driven, autonomous grid UI.

Usage:
    python run_reactor.py
- **Depends on**: office_converter.grid.reactor.reactor_app

## temp_verify.py
- **Path**: `temp_verify.py`
- **Lines**: 0

## test_all.py
- **Path**: `test_all.py`
- **Lines**: 98
- **Functions**: run_tests
- **Purpose**: Comprehensive Test Script for Office Converter
- **Depends on**: office_converter.utils.config, office_converter.utils.localization, office_converter.utils.pdf_tools, office_converter.converters

## validate_core.py
- **Path**: `validate_core.py`
- **Lines**: 117
- **Functions**: test_basic_functionality
- **Purpose**: Quick validation script for core data structures.

Run with: python validate_core.py

## validate_shim.py
- **Path**: `validate_shim.py`
- **Lines**: 128
- **Functions**: validate
- **Purpose**: Validate Shim Layer - Comprehensive Test

This script demonstrates that the shim layer successfully neutralizes
legacy UI modules without deleting any files.

Run: python validate_shim.py

