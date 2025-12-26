# SCRIPT Layer Context

This chunk contains 5 modules related to script.

## auto_commit.py
- **Path**: `scripts\auto_commit.py`
- **Lines**: 89
- **Functions**: get_current_version, bump_version, update_version_in_file, git_commit, main
- **Purpose**: Auto-commit script with version bump
Usage: python scripts/auto_commit.py "commit message"

## auto_save.py
- **Path**: `scripts\auto_save.py`
- **Lines**: 70
- **Functions**: bump_version, git_commit

## benchmark.py
- **Path**: `scripts\benchmark.py`
- **Lines**: 86
- **Functions**: benchmark_legacy_import, benchmark_reactor_import, benchmark_grid_init, main
- **Purpose**: Performance Benchmark: Legacy UI vs Reactor UI
Measures startup time and basic initialization.

## check_code.py
- **Path**: `scripts\check_code.py`
- **Lines**: 182
- **Functions**: print_header, print_result, run_command, check_syntax, check_ruff, check_imports, check_tests, main
- **Purpose**: Post-Code Check Script for Office Converter
============================================
Run: python scripts/check_code.py [--quick] [--fix]

## context_mapper.py
- **Path**: `scripts\context_mapper.py`
- **Lines**: 391
- **Classes**: ModuleInfo, DependencyGraph, ASTAnalyzer
- **Functions**: categorize_module, analyze_file, build_dependency_graph, generate_context_chunks, generate_markdown_report, generate_json_output, main
- **Purpose**: Project Context Mapper - AST-based Dependency Graph Generator
=============================================================
Creates an "architecture map" of the entire project by:
1. Parsing all Pytho

