# TEST Layer Context

This chunk contains 11 modules related to test.

## conftest.py
- **Path**: `tests\conftest.py`
- **Lines**: 168
- **Functions**: mock_com_object, mock_worker, mock_psutil, temp_dir, sample_pdf, pytest_configure
- **Purpose**: Enhanced Pytest Configuration - Military-Grade Fixtures

Comprehensive test infrastructure with:
- COM object mocking
- Worker process simulation
- System resource mocking (psutil)
- Hypothesis strate

## test_bug_fixes.py
- **Path**: `tests\test_bug_fixes.py`
- **Lines**: 130
- **Classes**: TestParsePageRange, TestPdfToolsImports, TestMainWindowButtons, TestExceptionHandling
- **Purpose**: Tests for bug fixes in Office Converter.

## test_core.py
- **Path**: `tests\test_core.py`
- **Lines**: 97
- **Classes**: TestImports, TestConfig, TestPdfTools, TestConverters
- **Purpose**: Unit tests for Office Converter.

## test_file_tools.py
- **Path**: `tests\test_file_tools.py`
- **Lines**: 199
- **Classes**: TestFileTools
- **Depends on**: office_converter.core.file_tools

## test_grid_core.py
- **Path**: `tests\test_grid_core.py`
- **Lines**: 616
- **Classes**: TestPriority, TestConversionFile, TestClusteredPriorityQueue, TestBloomFilterQuarantine, TestCircuitBreakerState, TestIntegration
- **Functions**: temp_files
- **Purpose**: Comprehensive Test Suite for Core Data Structures

Tests verify:
1. Algorithmic complexity guarantees (O(log n), O(1))
2. Thread safety under concurrent access
3. Context-aware clustering behavior
4. 

## test_grid_phase2.py
- **Path**: `tests\test_grid_phase2.py`
- **Lines**: 390
- **Classes**: TestCircuitBreakerCoordinator, TestWorkerPool, TestConversionGrid, TestStress
- **Functions**: temp_test_file, mock_converter
- **Purpose**: Test Suite for Worker Pool & Circuit Breaker (Phase 2)

Tests verify:
1. Worker process isolation and COM independence
2. Hot spare failover (<500ms recovery time)
3. Circuit breaker aggregation acros

## test_integration.py
- **Path**: `tests\test_integration.py`
- **Lines**: 367
- **Classes**: TestQueueIntegration, TestTemporaryFileFiltering, TestStateTransitions, TestErrorPropagation
- **Purpose**: Phase 4: Integration Tests - Queue & State Management

Tests that validate component integration and state consistency.

Focus Areas:
- FileQueue → Worker → ResultQueue flow
- Temporary file filtering

## test_performance.py
- **Path**: `tests\test_performance.py`
- **Lines**: 285
- **Classes**: TestBackgroundPDFPreview, TestVirtualFileList, TestAppendOnlyLog, TestCOMPoolHealthCheck, TestLazyImports, TestPerformanceBenchmarks, TestIntegration
- **Purpose**: Comprehensive Performance and Integration Tests
=================================================
Tests for Month 2 optimization items and overall system health.

## test_property_based.py
- **Path**: `tests\test_property_based.py`
- **Lines**: 369
- **Classes**: TestAdaptiveTimeoutProperties, TestMemoryThresholdProperties, TestBatchSplittingProperties, TestFileTypeDetectionProperties, TestHashCalculationProperties, TestSchedulerPriorityProperties
- **Purpose**: Phase 2: Property-Based Testing with Hypothesis

Logic Stress Testing for Utils and Calculations.

Tests use Hypothesis to generate thousands of random inputs and verify
mathematical invariants hold t

## test_resilience.py
- **Path**: `tests\test_resilience.py`
- **Lines**: 360
- **Classes**: TestZombieProcessHandling, TestCOMCrashHandling, TestMemoryLeakDetection, TestQueueOverflowProtection
- **Purpose**: Phase 3: Resilience Tests - Mocking Failures

Tests that validate failure handling and recovery mechanisms.

Scenarios:
A. Zombie Process Detection & Termination
B. COM Crash Handling
C. Memory Leak D

## test_shim.py
- **Path**: `tests\test_shim.py`
- **Lines**: 155
- **Classes**: TestShimLayer
- **Purpose**: Test Suite for Shim Layer

Verifies that import hook correctly neutralizes legacy UI modules.

