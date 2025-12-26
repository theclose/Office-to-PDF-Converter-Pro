# CONTROLLER Layer Context

This chunk contains 22 modules related to controller.

## __init__.py
- **Path**: `converters\__init__.py`
- **Lines**: 80
- **Functions**: __getattr__
- **Purpose**: Lazy-loads converter classes on first access to improve app startup time.
Heavy COM-dependent modules are only loaded when actually needed.

## base.py
- **Path**: `converters\base.py`
- **Lines**: 194
- **Classes**: BaseConverter
- **Functions**: ensure_com_initialized, release_com, get_converter_for_file, get_best_converter
- **Purpose**: Base Converter - Abstract class for all Office converters.
All specific converters (Excel, Word, PPT) inherit from this.

## excel.py
- **Path**: `converters\excel.py`
- **Lines**: 392
- **Classes**: ExcelConverter
- **Purpose**: Excel Converter - Converts Excel files to PDF using COM automation.
Uses COM Pool for connection reuse and memory optimization.
- **Depends on**: office_converter.utils.com_pool

## libreoffice.py
- **Path**: `converters\libreoffice.py`
- **Lines**: 200
- **Classes**: LibreOfficeConverter
- **Functions**: find_libreoffice, is_libreoffice_available, get_libreoffice_version
- **Purpose**: LibreOffice Converter - Fallback converter when MS Office is not available.
Uses LibreOffice in headless mode for document conversion.

Requirements:
- LibreOffice must be installed (https://www.libre

## ppt.py
- **Path**: `converters\ppt.py`
- **Lines**: 136
- **Classes**: PPTConverter
- **Purpose**: PowerPoint Converter - Converts presentations to PDF using COM automation.

## word.py
- **Path**: `converters\word.py`
- **Lines**: 159
- **Classes**: WordConverter
- **Purpose**: Word Converter - Converts Word documents to PDF using COM automation.

## __init__.py
- **Path**: `grid\__init__.py`
- **Lines**: 55
- **Purpose**: Autonomous Conversion Grid - Core Module

High-performance, fault-tolerant document conversion system.

Architecture:
- Clustered Priority Queue (Min-Heap) for O(log n) scheduling
- Bloom Filter for O

## circuit_breaker.py
- **Path**: `grid\circuit_breaker.py`
- **Lines**: 262
- **Classes**: CircuitBreakerConfig, CircuitBreakerCoordinator
- **Purpose**: Circuit Breaker Coordinator - Cross-Worker Failure Tracking

Aggregates circuit breaker states across all workers to implement
grid-wide quarantine decisions.

Problem:
- Each worker has its own circu

## grid.py
- **Path**: `grid\grid.py`
- **Lines**: 405
- **Classes**: ConversionGrid
- **Purpose**: Conversion Grid Controller - High-Level Orchestration

Integrates all components into a unified conversion system:
- Scheduler: Clustered priority queue
- Worker Pool: Multi-process execution with hot

## models.py
- **Path**: `grid\models.py`
- **Lines**: 273
- **Classes**: FileType, Priority, ConversionFile, CircuitBreakerState
- **Purpose**: Core Data Models for Conversion Grid

Defines immutable data structures with strong typing and validation.

## pool.py
- **Path**: `grid\pool.py`
- **Lines**: 606
- **Classes**: PoolState, PoolConfig, WorkerInfo, WorkerPool
- **Purpose**: Worker Pool - Multi-Process Conversion Grid with Hot Spare

Manages a pool of worker processes with:
- Dynamic scaling (add/remove workers)
- Hot spare for zero-downtime failover
- Health monitoring a

## quarantine.py
- **Path**: `grid\quarantine.py`
- **Lines**: 327
- **Classes**: BloomFilterQuarantine
- **Purpose**: Bloom Filter Quarantine System

Space-efficient quarantine tracking with O(1) lookup complexity.
Used to blacklist files that repeatedly crash converters.

Performance Characteristics:
- Insert: O(k) 

## __init__.py
- **Path**: `grid\reactor\__init__.py`
- **Lines**: 30
- **Purpose**: Reactor UI Module - Event-Driven Architecture

Phase 3: Decoupled UI with Command Pattern and Event Bus.

Components:
- commands.py: Command Pattern (UI actions → Commands → Grid)
- events.py: Event B

## bridge.py
- **Path**: `grid\reactor\bridge.py`
- **Lines**: 192
- **Classes**: GridBridge
- **Purpose**: GridBridge - Connects ConversionGrid to UI Events

Translates grid callbacks into EventBus events for reactive UI updates.

Architecture:
┌─────────────┐
│    Grid     │ (Phase 2 - Worker Pool)
└─────

## commands.py
- **Path**: `grid\reactor\commands.py`
- **Lines**: 474
- **Classes**: CommandResult, ExecutionContext, Command, AddFilesCommand, RemoveFilesCommand, ClearQueueCommand, StartConversionCommand, StopConversionCommand, ResetCircuitBreakerCommand, CommandBus
- **Purpose**: Command Pattern - Decouple UI actions from Grid execution

All user actions flow through Commands:
- User clicks button → Create Command → Post to CommandBus
- CommandBus executes async in background 

## events.py
- **Path**: `grid\reactor\events.py`
- **Lines**: 383
- **Classes**: Event, FileAddedEvent, FileCompletedEvent, FileFailedEvent, ProgressEvent, WorkerDeathEvent, LoadSheddingEvent, QuarantineEvent, CircuitBreakerEvent, EventBus, EventAggregator
- **Purpose**: Event System - Pub/Sub for Grid → UI Communication

Grid emits events when work completes:
- Worker completes file → FileCompletedEvent
- Worker fails file → FileFailedEvent
- Progress updates → Progr

## optimistic.py
- **Path**: `grid\reactor\optimistic.py`
- **Lines**: 217
- **Classes**: OptimisticItem, OptimisticState
- **Purpose**: Optimistic State Management - Instant UI Feedback

Provides immediate UI updates while background operations complete.

Flow:
1. User action → Create optimistic item with temp ID
2. UI shows optimisti

## reactor_app.py
- **Path**: `grid\reactor\reactor_app.py`
- **Lines**: 466
- **Classes**: ReactorApp
- **Functions**: main
- **Purpose**: ReactorApp - Main Application Window

Event-driven UI with Command Pattern and reactive updates.

Features:
- CustomTkinter modern UI
- VirtualListView for file display
- Command-based actions (non-bl

## virtual_list.py
- **Path**: `grid\reactor\virtual_list.py`
- **Lines**: 389
- **Classes**: VirtualListConfig, VirtualListView
- **Functions**: default_file_renderer
- **Purpose**: Virtual List Widget - O(1) Memory Rendering for Large Lists

Renders only visible items in viewport, regardless of total item count.

Key Features:
- Widget recycling (fixed pool of 20 widgets)
- Smoo

## scheduler.py
- **Path**: `grid\scheduler.py`
- **Lines**: 293
- **Classes**: ClusteredPriorityQueue
- **Purpose**: Clustered Priority Queue - Min-Heap Scheduler

Context-aware batch scheduling with O(log n) complexity.
Groups files by type to minimize COM initialization overhead.

Performance Characteristics:
- In

## shim.py
- **Path**: `grid\shim.py`
- **Lines**: 373
- **Classes**: ShimLoader, LegacyUIShim
- **Functions**: install_shim_layer, uninstall_shim_layer, is_shim_installed, verify_neutralization, get_shim_stats
- **Purpose**: Shim Layer - Import Hook for Legacy UI Neutralization

Intercepts imports of legacy UI modules and returns stub modules instead.
This allows us to logically isolate legacy code WITHOUT physically dele

## worker.py
- **Path**: `grid\worker.py`
- **Lines**: 437
- **Classes**: WorkerConfig, WorkerProcess
- **Purpose**: Worker Process - Isolated Conversion Executor

Each worker runs in a separate process to:
1. Isolate COM crashes (one worker dies, others continue)
2. Enable parallel processing across CPU cores
3. Im

