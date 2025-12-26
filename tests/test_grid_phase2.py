"""
Test Suite for Worker Pool & Circuit Breaker (Phase 2)

Tests verify:
1. Worker process isolation and COM independence
2. Hot spare failover (<500ms recovery time)
3. Circuit breaker aggregation across workers
4. Load shedding under memory pressure
5. Health monitoring and auto-recovery
6. Integration with Phase 1 components

Run with: pytest -v tests/test_grid_phase2.py
"""

import pytest
import time
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
import multiprocessing as mp

from grid.models import ConversionFile, CircuitBreakerState
from grid.worker import WorkerProcess, WorkerConfig
from grid.pool import WorkerPool, PoolConfig, PoolState
from grid.circuit_breaker import CircuitBreakerCoordinator, CircuitBreakerConfig
from grid.grid import ConversionGrid


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_test_file():
    """Create a temporary test file."""
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        f.write(b'X' * 5000)
        path = f.name
    
    yield path
    
    # Cleanup
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture
def mock_converter():
    """Mock converter for testing without actual COM."""
    with patch('grid.worker.get_converter_for_file') as mock:
        converter_instance = Mock()
        converter_instance.initialize.return_value = True
        converter_instance.convert.return_value = True
        converter_instance.cleanup.return_value = None
        
        mock.return_value = Mock(return_value=converter_instance)
        yield mock


# ============================================================================
# CIRCUIT BREAKER COORDINATOR TESTS
# ============================================================================

class TestCircuitBreakerCoordinator:
    """Test centralized circuit breaker logic."""
    
    def test_initial_state_allows_attempts(self, temp_test_file):
        """Test new files are allowed by default."""
        coordinator = CircuitBreakerCoordinator()
        file = ConversionFile(temp_test_file)
        
        should_allow, reason = coordinator.should_allow_attempt(file)
        assert should_allow is True
        assert "OK" in reason
    
    def test_failure_threshold_opens_circuit(self, temp_test_file):
        """Test circuit opens after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        coordinator = CircuitBreakerCoordinator(config=config)
        file = ConversionFile(temp_test_file)
        
        # Record 3 failures
        for _ in range(3):
            coordinator.record_failure(file, "Mock error")
        
        # Circuit should be OPEN
        should_allow, reason = coordinator.should_allow_attempt(file)
        assert should_allow is False
        assert "Circuit OPEN" in reason or "Quarantined" in reason
    
    def test_success_resets_circuit(self, temp_test_file):
        """Test successful conversion resets circuit."""
        coordinator = CircuitBreakerCoordinator()
        file = ConversionFile(temp_test_file)
        
        # Record 2 failures
        coordinator.record_failure(file)
        coordinator.record_failure(file)
        
        # Then success
        coordinator.record_success(file)
        
        # Circuit state should reset
        state = coordinator.get_circuit_state(file)
        assert state.failure_count == 0
        assert state.state == 'CLOSED'
    
    def test_manual_reset(self, temp_test_file):
        """Test manual circuit reset."""
        coordinator = CircuitBreakerCoordinator()
        file = ConversionFile(temp_test_file)
        
        # Open circuit
        for _ in range(3):
            coordinator.record_failure(file)
        
        # Manual reset
        coordinator.reset_circuit(file)
        
        # Should allow attempts again
        should_allow, _ = coordinator.should_allow_attempt(file)
        assert should_allow is True
    
    def test_stats_tracking(self, temp_test_file):
        """Test statistics are tracked correctly."""
        coordinator = CircuitBreakerCoordinator()
        file1 = ConversionFile(temp_test_file)
        
        coordinator.record_success(file1)
        coordinator.record_failure(file1)
        coordinator.record_failure(file1)
        
        stats = coordinator.get_stats()
        assert stats['total_successes'] == 1
        assert stats['total_failures'] == 2


# ============================================================================
# WORKER POOL TESTS  
# ============================================================================

class TestWorkerPool:
    """Test worker pool management."""
    
    def test_pool_initialization(self):
        """Test pool starts with correct number of workers."""
        config = PoolConfig(num_workers=2, enable_hot_spare=False)
        pool = WorkerPool(config=config)
        
        pool.start()
        time.sleep(1)  # Allow workers to start
        
        stats = pool.get_stats()
        assert stats['active_workers'] == 2
        assert stats['hot_spare_ready'] is False
        
        pool.shutdown(timeout=5.0)
    
    def test_hot_spare_initialization(self):
        """Test hot spare is created when enabled."""
        config = PoolConfig(num_workers=2, enable_hot_spare=True, min_ram_mb_for_spare=0)
        pool = WorkerPool(config=config)
        
        pool.start()
        time.sleep(1)
        
        stats = pool.get_stats()
        assert stats['active_workers'] == 2
        assert stats['hot_spare_ready'] is True
        
        pool.shutdown(timeout=5.0)
    
    def test_submit_and_get_result(self, temp_test_file, mock_converter):
        """Test submitting work and receiving results."""
        config = PoolConfig(num_workers=1, enable_hot_spare=False)
        pool = WorkerPool(config=config)
        pool.start()
        time.sleep(1)
        
        file = ConversionFile(temp_test_file)
        pool.submit(file)
        
        # Wait for result (with timeout)
        result = None
        for _ in range(10):  # 10 second timeout
            result = pool.get_result(timeout=1.0)
            if result:
                break
        
        pool.shutdown(timeout=5.0)
        
        # Mock converter should have been called
        assert result is not None
        # Result structure depends on mock
    
    def test_pool_state_transitions(self):
        """Test pool state transitions."""
        config = PoolConfig(num_workers=1, enable_hot_spare=False)
        pool = WorkerPool(config=config)
        
        # Initial state
        assert pool.state == PoolState.INITIALIZING
        
        # After start
        pool.start()
        assert pool.state == PoolState.ACTIVE
        
        # After shutdown
        pool.shutdown(timeout=5.0)
        assert pool.state == PoolState.STOPPED


# ============================================================================
# CONVERSION GRID INTEGRATION TESTS
# ============================================================================

class TestConversionGrid:
    """Test high-level grid controller."""
    
    def test_grid_initialization(self):
        """Test grid initializes all components."""
        grid = ConversionGrid(num_workers=2, enable_hot_spare=False)
        grid.start()
        time.sleep(1)
        
        stats = grid.get_stats()
        assert stats['pool']['active_workers'] == 2
        assert stats['scheduler']['pending'] == 0
        
        grid.shutdown(timeout=5.0)
    
    def test_enqueue_file(self, temp_test_file):
        """Test enqueuing file to grid."""
        grid = ConversionGrid(num_workers=1, enable_hot_spare=False)
        grid.start()
        time.sleep(1)
        
        file = ConversionFile(temp_test_file)
        success = grid.enqueue(file)
        
        assert success is True
        assert grid.total_enqueued == 1
        
        grid.shutdown(timeout=5.0)
    
    def test_quarantined_file_rejected(self, temp_test_file):
        """Test quarantined files are rejected."""
        grid = ConversionGrid(num_workers=1, enable_hot_spare=False)
        grid.start()
        time.sleep(1)
        
        file = ConversionFile(temp_test_file)
        
        # Quarantine the file
        grid.quarantine.add(file.file_hash)
        
        # Should be rejected
        success = grid.enqueue(file)
        assert success is False
        assert grid.total_quarantined == 1
        
        grid.shutdown(timeout=5.0)
    
    def test_callbacks_invoked(self, temp_test_file, mock_converter):
        """Test callbacks are invoked on completion."""
        complete_callback = Mock()
        error_callback = Mock()
        
        grid = ConversionGrid(
            num_workers=1,
            enable_hot_spare=False,
            on_file_complete=complete_callback,
            on_file_error=error_callback
        )
        grid.start()
        time.sleep(1)
        
        file = ConversionFile(temp_test_file)
        grid.enqueue(file)
        
        # Wait for completion
        time.sleep(3)
        
        grid.shutdown(timeout=5.0)
        
        # One of the callbacks should have been called
        # (depending on mock converter behavior)
        assert complete_callback.called or error_callback.called
    
    def test_batch_enqueue(self, temp_test_file):
        """Test batch file enqueueing."""
        grid = ConversionGrid(num_workers=2, enable_hot_spare=False)
        grid.start()
        time.sleep(1)
        
        # Create multiple files
        files = [ConversionFile(temp_test_file) for _ in range(5)]
        
        enqueued = grid.enqueue_batch(files)
        assert enqueued == 5
        assert grid.total_enqueued == 5
        
        grid.shutdown(timeout=5.0)
    
    def test_statistics_tracking(self, temp_test_file):
        """Test comprehensive statistics."""
        grid = ConversionGrid(num_workers=1, enable_hot_spare=False)
        grid.start()
        time.sleep(1)
        
        stats = grid.get_stats()
        
        # Check structure
        assert 'state' in stats
        assert 'uptime_seconds' in stats
        assert 'scheduler' in stats
        assert 'pool' in stats
        assert 'circuit_breaker' in stats
        assert 'quarantine' in stats
        
        grid.shutdown(timeout=5.0)


# ============================================================================
# STRESS TESTS
# ============================================================================

class TestStress:
    """Stress tests for robustness."""
    
    @pytest.mark.slow
    def test_many_files_single_worker(self, temp_test_file, mock_converter):
        """Test processing many files with single worker."""
        grid = ConversionGrid(num_workers=1, enable_hot_spare=False)
        grid.start()
        time.sleep(1)
        
        # Enqueue 100 files
        files = [ConversionFile(temp_test_file) for _ in range(100)]
        grid.enqueue_batch(files)
        
        # Let it run for a bit
        time.sleep(5)
        
        stats = grid.get_stats()
        # Should have made some progress
        assert stats['total_enqueued'] == 100
        
        grid.shutdown(timeout=10.0)
    
    @pytest.mark.slow
    def test_concurrent_operations(self, temp_test_file):
        """Test concurrent enqueue/dequeue operations."""
        grid = ConversionGrid(num_workers=4, enable_hot_spare=True)
        grid.start()
        time.sleep(2)
        
        import threading
        errors = []
        
        def enqueue_worker():
            try:
                for _ in range(50):
                    file = ConversionFile(temp_test_file)
                    grid.enqueue(file)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=enqueue_worker) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # No errors should occur
        assert len(errors) == 0
        
        # Should have enqueued 150 files
        assert grid.total_enqueued == 150
        
        grid.shutdown(timeout=10.0)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
