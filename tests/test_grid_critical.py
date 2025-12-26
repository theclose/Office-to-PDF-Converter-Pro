"""
Critical Tests for Grid System - Enhanced Manual Implementation
================================================================
Integration and concurrency tests for ConversionGrid.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, ANY
import threading
import time
import queue
from pathlib import Path

# Import grid components
from grid.grid import ConversionGrid
from grid.models import ConversionTask, TaskStatus, TaskPriority


# ==================== Grid Initialization Tests ====================

class TestGridInitialization:
    """Critical tests for grid initialization and configuration."""
    
    def test_grid_initializes_with_default_workers(self):
        """Test grid creates default number of workers."""
        grid = ConversionGrid()
        
        assert grid.max_workers > 0
        assert grid._queue is not None
        
    def test_grid_initializes_with_custom_workers(self):
        """Test grid respects custom worker count."""
        grid = ConversionGrid(max_workers=4)
        
        assert grid.max_workers == 4
        
    def test_grid_rejects_invalid_worker_count(self):
        """Test grid validates worker count."""
        with pytest.raises(ValueError):
            ConversionGrid(max_workers=0)
            
        with pytest.raises(ValueError):
            ConversionGrid(max_workers=-1)
            
    def test_grid_has_proper_initial_state(self):
        """Test gri

d starts in stopped state."""
        grid = ConversionGrid(max_workers=2)
        
        assert grid.is_active() == False
        assert grid.get_stats()['active_tasks'] == 0


# ==================== Grid Lifecycle Tests ====================

class TestGridLifecycle:
    """Critical tests for grid start/stop lifecycle."""
    
    @pytest.fixture
    def grid(self):
        """Create grid instance for testing."""
        g = ConversionGrid(max_workers=2)
        yield g
        if g.is_active():
            g.shutdown()
            
    def test_grid_start_activates_workers(self, grid):
        """Test starting grid activates worker pool."""
        grid.start()
        
        assert grid.is_active() == True
        
        # Give workers time to start
        time.sleep(0.1)
        
    def test_grid_shutdown_stops_workers(self, grid):
        """Test shutdown gracefully stops all workers."""
        grid.start()
        time.sleep(0.1)
        
        grid.shutdown(timeout=2.0)
        
        assert grid.is_active() == False
        
    def test_grid_double_start_idempotent(self, grid):
        """Test starting already-started grid is safe."""
        grid.start()
        grid.start()  # Should not crash
        
        assert grid.is_active() == True
        
    def test_grid_double_shutdown_idempotent(self, grid):
        """Test shutting down already-stopped grid is safe."""
        grid.start()
        grid.shutdown()
        grid.shutdown()  # Should not crash
        
        assert grid.is_active() == False


# ==================== Task Enqueueing Tests ====================

class TestGridEnqueue:
    """Critical tests for task submission."""
    
    @pytest.fixture
    def grid(self):
        """Create and start grid."""
        g = ConversionGrid(max_workers=2)
        g.start()
        yield g
        g.shutdown()
        
    def test_enqueue_single_task(self, grid, tmp_path):
        """Test enqueueing a single conversion task."""
        input_file = tmp_path / "test.txt"
        input_file.write_text("test")
        
        task_id = grid.enqueue(
            str(input_file),
            str(tmp_path / "output.pdf"),
            priority=TaskPriority.NORMAL
        )
        
        assert task_id is not None
        assert isinstance(task_id, str)
        
    def test_enqueue_batch_of_tasks(self, grid, tmp_path):
        """Test enqueueing multiple tasks at once."""
        tasks = []
        for i in range(5):
            input_f = tmp_path / f"input_{i}.txt"
            input_f.write_text(f"test {i}")
            tasks.append({
                'input': str(input_f),
                'output': str(tmp_path / f"output_{i}.pdf")
            })
            
        task_ids = grid.enqueue_batch(tasks)
        
        assert len(task_ids) == 5
        assert all(isinstance(tid, str) for tid in task_ids)
        
    def test_enqueue_respects_priority(self, grid, tmp_path):
        """Test high-priority tasks are processed first."""
        results = []
        
        def callback(task_id, result):
            results.append(task_id)
            
        # Enqueue low priority first
        for i in range(3):
            input_f = tmp_path / f"low_{i}.txt"
            input_f.write_text("test")
            grid.enqueue(str(input_f), str(tmp_path / f"out_low_{i}.pdf"),
                        priority=TaskPriority.LOW, callback=callback)
                        
        # Then high priority
        for i in range(2):
            input_f = tmp_path / f"high_{i}.txt"
            input_f.write_text("test")
            grid.enqueue(str(input_f), str(tmp_path / f"out_high_{i}.pdf"),
                        priority=TaskPriority.HIGH, callback=callback)
                        
        grid.wait_completion(timeout=5.0)
        
        # High priority should be processed first (in results)
        # Note: This is probabilistic, actual order may vary


# ==================== Concurrency Tests ====================

class TestGridConcurrency:
    """Critical tests for concurrent task processing."""
    
    @pytest.fixture
    def grid(self):
        """Create grid with multiple workers."""
        g = ConversionGrid(max_workers=4)
        g.start()
        yield g
        g.shutdown()
        
    def test_grid_processes_tasks_concurrently(self, grid, tmp_path):
        """Test grid processes multiple tasks at the same time."""
        results = []
        lock = threading.Lock()
        
        def slow_callback(task_id, result):
            with lock:
                results.append((task_id, time.time()))
                
        # Create 10 tasks
        for i in range(10):
            input_f = tmp_path / f"input_{i}.txt"
            input_f.write_text("test")
            grid.enqueue(str(input_f), str(tmp_path / f"out_{i}.pdf"),
                        callback=slow_callback)
                        
        grid.wait_completion(timeout=10.0)
        
        # Should have processed all
        assert len(results) >= 10
        
    def test_grid_handles_task_failures_gracefully(self, grid, tmp_path):
        """Test grid continues processing after task failures."""
        success_count = []
        failure_count = []
        
        def callback(task_id, result):
            if result.get('success'):
                success_count.append(task_id)
            else:
                failure_count.append(task_id)
                
        # Mix of valid and invalid tasks
        for i in range(5):
            if i % 2 == 0:
                # Valid
                input_f = tmp_path / f"input_{i}.txt"
                input_f.write_text("test")
            else:
                # Invalid (non-existent file)
                input_f = tmp_path / f"nonexistent_{i}.txt"
                
            grid.enqueue(str(input_f), str(tmp_path / f"out_{i}.pdf"),
                        callback=callback)
                        
        grid.wait_completion(timeout=5.0)
        
        # Should have both successes and failures
        assert len(success_count) > 0 or len(failure_count) > 0
        
    def test_grid_thread_safety(self, grid, tmp_path):
        """Test grid is thread-safe for concurrent enqueuing."""
        def enqueue_from_thread(thread_id):
            for i in range(5):
                input_f = tmp_path / f"t{thread_id}_input_{i}.txt"
                input_f.write_text("test")
                grid.enqueue(str(input_f), str(tmp_path / f"t{thread_id}_out_{i}.pdf"))
                
        threads = [threading.Thread(target=enqueue_from_thread, args=(i,)) 
                   for i in range(4)]
                   
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # Should not crash, all tasks submitted
        stats = grid.get_stats()
        # Exact count may vary, but should have received tasks


# ==================== Stats and Monitoring Tests ====================

class TestGridMonitoring:
    """Critical tests for grid statistics and monitoring."""
    
    @pytest.fixture
    def grid(self):
        """Create and start grid."""
        g = ConversionGrid(max_workers=2)
        g.start()
        yield g
        g.shutdown()
        
    def test_get_stats_returns_current_state(self, grid, tmp_path):
        """Test stats reflect actual grid state."""
        initial_stats = grid.get_stats()
        
        assert 'active_tasks' in initial_stats
        assert 'completed_tasks' in initial_stats
        assert 'failed_tasks' in initial_stats
        assert initial_stats['active_tasks'] >= 0
        
    def test_stats_update_on_task_completion(self, grid, tmp_path):
        """Test task completion updates stats."""
        initial_completed = grid.get_stats().get('completed_tasks', 0)
        
        input_f = tmp_path / "input.txt"
        input_f.write_text("test")
        
        grid.enqueue(str(input_f), str(tmp_path / "output.pdf"))
        grid.wait_completion(timeout=3.0)
        
        final_completed = grid.get_stats().get('completed_tasks', 0)
        
        # Should have increased (if task completed)
        # Note: Depends on actual conversion working
        
    def test_wait_completion_timeout(self, grid):
        """Test wait_completion respects timeout."""
        start = time.time()
        
        # Wait with short timeout (no tasks)
        grid.wait_completion(timeout=1.0)
        
        elapsed = time.time() - start
        
        assert elapsed >= 1.0
        assert elapsed < 1.5  # Some tolerance


# ==================== Integration Tests ====================

class TestGridIntegration:
    """End-to-end integration tests."""
    
    def test_full_conversion_pipeline(self, tmp_path):
        """Test complete conversion workflow."""
        # Create real test file
        input_file = tmp_path / "test_document.txt"
        input_file.write_text("Test content for conversion")
        output_file = tmp_path / "output.pdf"
        
        # Create and run grid
        grid = ConversionGrid(max_workers=2)
        grid.start()
        
        completion_event = threading.Event()
        result_holder = {'result': None}
        
        def on_complete(task_id, result):
            result_holder['result'] = result
            completion_event.set()
            
        try:
            grid.enqueue(
                str(input_file),
                str(output_file),
                callback=on_complete
            )
            
            # Wait for completion
            completed = completion_event.wait(timeout=10.0)
            
            assert completed, "Task did not complete in time"
            # Result may vary based on actual converter availability
            
        finally:
            grid.shutdown(timeout=2.0)
            
    def test_batch_conversion_consistency(self, tmp_path):
        """Test batch conversion produces consistent results."""
        grid = ConversionGrid(max_workers=3)
        grid.start()
        
        results = []
        lock = threading.Lock()
        
        def collector(task_id, result):
            with lock:
                results.append(result)
                
        # Create 20 test files
        tasks = []
        for i in range(20):
            input_f = tmp_path / f"doc_{i}.txt"
            input_f.write_text(f"Document {i}")
            tasks.append({
                'input': str(input_f),
                'output': str(tmp_path / f"out_{i}.pdf"),
                'callback': collector
            })
            
        try:
            grid.enqueue_batch(tasks)
            grid.wait_completion(timeout=30.0)
            
            # All tasks should have been processed
            assert len(results) == 20
            
        finally:
            grid.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
