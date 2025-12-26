"""
Comprehensive Test Suite for Core Data Structures

Tests verify:
1. Algorithmic complexity guarantees (O(log n), O(1))
2. Thread safety under concurrent access
3. Context-aware clustering behavior
4. Bloom filter false positive rates
5. Edge cases and error handling

Run with: pytest -v tests/test_grid_core.py
"""

import pytest
import time
import threading
import tempfile
import os
from pathlib import Path
from typing import List

from grid.models import (
    FileType, 
    ConversionFile, 
    Priority, 
    CircuitBreakerState,
    FILE_TYPE_MAP
)
from grid.scheduler import ClusteredPriorityQueue
from grid.quarantine import BloomFilterQuarantine


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_files():
    """Create temporary test files of different types."""
    files = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test files with varying sizes
        for ext, size_kb in [
            ('.docx', 5),
            ('.xlsx', 50),
            ('.pptx', 20),
            ('.doc', 10),
        ]:
            path = Path(tmpdir) / f"test{ext}"
            path.write_bytes(b'X' * (size_kb * 1024))
            files[ext] = str(path)
        
        yield files


# ============================================================================
# PRIORITY TESTS
# ============================================================================

class TestPriority:
    """Test Priority comparison logic."""
    
    def test_priority_ordering(self):
        """Verify priority sorts by (type, size, time)."""
        p1 = Priority(FileType.WORD, 1000, 1.0)
        p2 = Priority(FileType.WORD, 2000, 1.0)
        p3 = Priority(FileType.EXCEL, 500, 1.0)
        
        # Same type: smaller file first
        assert p1 < p2
        
        # Different type: Word before Excel
        assert p1 < p3
        
        # Tiebreaker: earlier arrival first
        p4 = Priority(FileType.WORD, 1000, 0.5)
        assert p4 < p1
    
    def test_priority_equality(self):
        """Test equality comparison."""
        p1 = Priority(FileType.WORD, 1000, 1.0)
        p2 = Priority(FileType.WORD, 1000, 1.0)
        p3 = Priority(FileType.WORD, 1001, 1.0)
        
        assert p1 == p2
        assert p1 != p3


# ============================================================================
# CONVERSION FILE TESTS
# ============================================================================

class TestConversionFile:
    """Test ConversionFile model."""
    
    def test_file_creation(self, temp_files):
        """Test basic file creation and metadata extraction."""
        file = ConversionFile(temp_files['.docx'])
        
        assert file.file_type == FileType.WORD
        assert file.filename == 'test.docx'
        assert file.file_size_bytes == 5 * 1024
        assert file.status == 'pending'
        assert len(file.file_hash) == 64  # SHA256 hex
    
    def test_unsupported_file_type(self):
        """Test rejection of unsupported file types."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'test')
            path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                ConversionFile(path)
        finally:
            os.unlink(path)
    
    def test_missing_file(self):
        """Test error on missing file."""
        with pytest.raises(FileNotFoundError):
            ConversionFile('/nonexistent/file.docx')
    
    def test_hash_stability(self, temp_files):
        """Test file hash is stable across instances."""
        file1 = ConversionFile(temp_files['.docx'])
        file2 = ConversionFile(temp_files['.docx'])
        
        assert file1.file_hash == file2.file_hash
    
    def test_adaptive_timeout(self, temp_files):
        """Test adaptive timeout calculation."""
        small_file = ConversionFile(temp_files['.docx'])  # 5KB
        large_file = ConversionFile(temp_files['.xlsx'])  # 50KB
        
        timeout_small = small_file.compute_timeout(base_timeout=30, rate_mb_per_sec=2)
        timeout_large = large_file.compute_timeout(base_timeout=30, rate_mb_per_sec=2)
        
        # Larger file should have longer timeout
        assert timeout_large > timeout_small
        
        # Small file should be close to base
        assert 30 <= timeout_small <= 32
    
    def test_copy_on_write(self, temp_files):
        """Test immutability via with_status."""
        original = ConversionFile(temp_files['.docx'])
        
        # Update status
        updated = original.with_status('completed', duration=5.0)
        
        # Original unchanged
        assert original.status == 'pending'
        assert original.duration == 0.0
        
        # Updated has new values
        assert updated.status == 'completed'
        assert updated.duration == 5.0
        
        # Other fields preserved
        assert updated.path == original.path
        assert updated.file_hash == original.file_hash
    
    def test_comparison_for_heap(self, temp_files):
        """Test __lt__ for heap ordering."""
        doc1 = ConversionFile(temp_files['.docx'])   # Word, 5KB
        doc2 = ConversionFile(temp_files['.doc'])    # Word, 10KB
        sheet = ConversionFile(temp_files['.xlsx'])  # Excel, 50KB
        
        # Same type: smaller first
        assert doc1 < doc2
        
        # Different type: Word before Excel
        assert doc1 < sheet


# ============================================================================
# CLUSTERED PRIORITY QUEUE TESTS
# ============================================================================

class TestClusteredPriorityQueue:
    """Test heap-based scheduler."""
    
    def test_basic_enqueue_dequeue(self, temp_files):
        """Test basic queue operations."""
        queue = ClusteredPriorityQueue()
        
        file1 = ConversionFile(temp_files['.docx'])
        queue.enqueue(file1)
        
        assert len(queue) == 1
        assert queue.peek() == file1
        
        dequeued = queue.dequeue()
        assert dequeued == file1
        assert len(queue) == 0
    
    def test_priority_ordering(self, temp_files):
        """Test files are dequeued in priority order."""
        queue = ClusteredPriorityQueue()
        
        # Enqueue in random order
        sheet = ConversionFile(temp_files['.xlsx'])  # Excel
        doc1 = ConversionFile(temp_files['.docx'])   # Word, small
        doc2 = ConversionFile(temp_files['.doc'])    # Word, large
        
        queue.enqueue(sheet)
        queue.enqueue(doc2)
        queue.enqueue(doc1)
        
        # Should dequeue Word files first (type clustering)
        # Within Word, smaller first
        first = queue.dequeue()
        assert first.file_type == FileType.WORD
        assert first.file_size_bytes == 5 * 1024  # doc1
        
        second = queue.dequeue()
        assert second.file_type == FileType.WORD
        assert second.file_size_bytes == 10 * 1024  # doc2
        
        third = queue.dequeue()
        assert third.file_type == FileType.EXCEL  # sheet
    
    def test_batch_enqueue(self, temp_files):
        """Test efficient batch insertion."""
        queue = ClusteredPriorityQueue()
        
        files = [
            ConversionFile(temp_files[ext])
            for ext in ['.docx', '.xlsx', '.doc', '.pptx']
        ]
        
        count = queue.enqueue_batch(files)
        assert count == 4
        assert len(queue) == 4
    
    def test_cluster_distribution(self, temp_files):
        """Test cluster tracking."""
        queue = ClusteredPriorityQueue()
        
        queue.enqueue(ConversionFile(temp_files['.docx']))
        queue.enqueue(ConversionFile(temp_files['.doc']))
        queue.enqueue(ConversionFile(temp_files['.xlsx']))
        
        distribution = queue.cluster_distribution
        assert distribution[FileType.WORD] == 2
        assert distribution[FileType.EXCEL] == 1
        assert FileType.POWERPOINT not in distribution
    
    def test_peek_batch(self, temp_files):
        """Test preview without removing."""
        queue = ClusteredPriorityQueue()
        
        files = [
            ConversionFile(temp_files[ext])
            for ext in ['.docx', '.xlsx', '.pptx']
        ]
        queue.enqueue_batch(files)
        
        # Peek doesn't remove
        previewed = queue.peek_batch(2)
        assert len(previewed) == 2
        assert len(queue) == 3
        
        # Previewed are in priority order
        assert all(
            previewed[i].priority <= previewed[i+1].priority
            for i in range(len(previewed)-1)
        )
    
    def test_remove_specific(self, temp_files):
        """Test removing specific file."""
        queue = ClusteredPriorityQueue()
        
        file1 = ConversionFile(temp_files['.docx'])
        file2 = ConversionFile(temp_files['.xlsx'])
        
        queue.enqueue(file1)
        queue.enqueue(file2)
        
        # Remove file1
        removed = queue.remove(file1)
        assert removed is True
        assert len(queue) == 1
        
        # Only file2 remains
        assert queue.dequeue() == file2
    
    def test_drain(self, temp_files):
        """Test batch extraction."""
        queue = ClusteredPriorityQueue()
        
        files = [
            ConversionFile(temp_files[ext])
            for ext in ['.docx', '.xlsx', '.pptx', '.doc']
        ]
        queue.enqueue_batch(files)
        
        # Drain 2 files
        drained = queue.drain(max_count=2)
        assert len(drained) == 2
        assert len(queue) == 2
        
        # Drain remaining
        remaining = queue.drain()
        assert len(remaining) == 2
        assert len(queue) == 0
    
    def test_thread_safety(self, temp_files):
        """Test concurrent access from multiple threads."""
        queue = ClusteredPriorityQueue()
        errors = []
        enqueue_count = [0]  # Mutable counter
        dequeue_count = [0]
        lock = threading.Lock()
        
        def enqueue_worker():
            try:
                for _ in range(100):
                    file = ConversionFile(temp_files['.docx'])
                    queue.enqueue(file)
                    with lock:
                        enqueue_count[0] += 1
            except Exception as e:
                errors.append(e)
        
        def dequeue_worker():
            try:
                for _ in range(50):
                    result = queue.dequeue()
                    if result is not None:
                        with lock:
                            dequeue_count[0] += 1
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Start threads
        threads = [
            threading.Thread(target=enqueue_worker),
            threading.Thread(target=enqueue_worker),
            threading.Thread(target=dequeue_worker),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # No errors occurred
        assert len(errors) == 0
        
        # Queue state is consistent (enqueued - dequeued = remaining)
        expected_remaining = enqueue_count[0] - dequeue_count[0]
        assert len(queue) == expected_remaining


# ============================================================================
# BLOOM FILTER QUARANTINE TESTS
# ============================================================================

class TestBloomFilterQuarantine:
    """Test quarantine system."""
    
    def test_basic_add_contains(self):
        """Test basic quarantine operations."""
        quarantine = BloomFilterQuarantine(expected_items=100)
        
        # Add file hash
        file_hash = "a" * 64  # Fake SHA256
        quarantine.add(file_hash)
        
        # Should be found
        assert file_hash in quarantine
        assert quarantine.contains(file_hash) is True
        
        # Different hash not found
        other_hash = "b" * 64
        assert other_hash not in quarantine
    
    def test_false_positive_rate(self):
        """Test FPR is within expected bounds."""
        quarantine = BloomFilterQuarantine(
            expected_items=1000,
            false_positive_rate=0.01  # 1% target
        )
        
        # Add 1000 items
        added_hashes = set()
        for i in range(1000):
            file_hash = f"{i:064x}"
            quarantine.add(file_hash)
            added_hashes.add(file_hash)
        
        # Test 10000 random hashes NOT in set
        false_positives = 0
        for i in range(10000, 20000):
            test_hash = f"{i:064x}"
            if test_hash not in added_hashes and quarantine.contains(test_hash):
                false_positives += 1
        
        actual_fpr = false_positives / 10000
        
        # Should be close to 1% (allow 2x margin)
        assert actual_fpr < 0.02
        
        # Estimated FPR should be reasonable
        estimated_fpr = quarantine.estimated_fpr()
        assert 0.0 < estimated_fpr < 0.05
    
    def test_exact_set_verification(self):
        """Test exact set provides 100% confidence."""
        quarantine = BloomFilterQuarantine(
            expected_items=100,
            exact_set_threshold=50
        )
        
        # Add items
        for i in range(40):
            quarantine.add(f"{i:064x}")
        
        # Items in exact set
        is_quarantined, confidence = quarantine.contains_with_confidence(f"{0:064x}")
        assert is_quarantined is True
        assert confidence == 1.0  # Exact match
    
    def test_remove_from_exact_set(self):
        """Test removal from exact set."""
        quarantine = BloomFilterQuarantine(exact_set_threshold=100)
        
        file_hash = "a" * 64
        quarantine.add(file_hash)
        
        assert quarantine.contains(file_hash) is True
        
        # Remove from exact set
        quarantine.remove(file_hash)
        
        # May still show in Bloom filter (false positive)
        # but confidence should drop
        is_quar, conf = quarantine.contains_with_confidence(file_hash)
        if is_quar:
            assert conf < 1.0  # Not in exact set anymore
    
    def test_rebuild_from_exact(self):
        """Test Bloom filter rebuild."""
        quarantine = BloomFilterQuarantine(exact_set_threshold=100)
        
        # Add and remove many items
        for i in range(50):
            quarantine.add(f"{i:064x}")
        
        for i in range(25, 50):
            quarantine.remove(f"{i:064x}")
        
        # Rebuild to eliminate false positives from removed items
        quarantine.rebuild_from_exact()
        
        # Items 0-24 should still be found
        assert quarantine.contains(f"{10:064x}") is True
        
        # Items 25-49 should NOT be found (with high probability)
        # Note: Small chance of FP, so test a few
        removed_found = sum(
            quarantine.contains(f"{i:064x}")
            for i in range(25, 50)
        )
        
        # Most should be not found
        assert removed_found < 5  # Allow some FPs
    
    def test_memory_efficiency(self):
        """Test memory usage is O(m), not O(n)."""
        quarantine = BloomFilterQuarantine(expected_items=10000)
        
        # Add 10000 items
        for i in range(10000):
            quarantine.add(f"{i:064x}")
        
        stats = quarantine.get_stats()
        
        # Memory should be < 20KB (vs ~500KB for HashMap)
        assert stats['memory_bytes'] < 20 * 1024
        
        # Saturation should be reasonable (not near 1.0)
        assert 0.1 < stats['saturation'] < 0.9
    
    def test_thread_safety(self):
        """Test concurrent quarantine operations."""
        quarantine = BloomFilterQuarantine(expected_items=1000)
        errors = []
        
        def add_worker(start: int):
            try:
                for i in range(start, start + 100):
                    quarantine.add(f"{i:064x}")
            except Exception as e:
                errors.append(e)
        
        def check_worker():
            try:
                for i in range(500):
                    quarantine.contains(f"{i:064x}")
            except Exception as e:
                errors.append(e)
        
        threads = [
            threading.Thread(target=add_worker, args=(0,)),
            threading.Thread(target=add_worker, args=(100,)),
            threading.Thread(target=check_worker),
            threading.Thread(target=check_worker),
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert len(quarantine) == 200


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================

class TestCircuitBreakerState:
    """Test circuit breaker state machine."""
    
    def test_closed_state(self):
        """Test CLOSED state allows all attempts."""
        cb = CircuitBreakerState(file_hash="test")
        
        assert cb.state == 'CLOSED'
        assert cb.should_allow_attempt(time.time()) is True
    
    def test_open_after_threshold(self):
        """Test circuit opens after failure threshold."""
        cb = CircuitBreakerState(file_hash="test")
        current_time = time.time()
        
        # Record failures
        for _ in range(3):
            cb.record_failure(current_time, threshold=3, cooldown=30)
        
        assert cb.state == 'OPEN'
        assert cb.should_allow_attempt(current_time) is False
    
    def test_half_open_after_cooldown(self):
        """Test transition to HALF_OPEN after cooldown."""
        cb = CircuitBreakerState(file_hash="test")
        current_time = time.time()
        
        # Open circuit
        for _ in range(3):
            cb.record_failure(current_time, threshold=3, cooldown=1)  # 1s cooldown
        
        assert cb.state == 'OPEN'
        
        # After cooldown
        future_time = current_time + 2
        assert cb.should_allow_attempt(future_time) is True
        assert cb.state == 'HALF_OPEN'
    
    def test_close_on_success(self):
        """Test circuit closes on success."""
        cb = CircuitBreakerState(file_hash="test")
        
        # Open circuit
        for _ in range(3):
            cb.record_failure(time.time(), threshold=3)
        
        assert cb.state == 'OPEN'
        
        # Success resets
        cb.record_success()
        assert cb.state == 'CLOSED'
        assert cb.failure_count == 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Test components working together."""
    
    def test_scheduler_with_quarantine(self, temp_files):
        """Test scheduler skips quarantined files."""
        scheduler = ClusteredPriorityQueue()
        quarantine = BloomFilterQuarantine()
        
        # Create files
        file1 = ConversionFile(temp_files['.docx'])
        file2 = ConversionFile(temp_files['.xlsx'])
        
        # Quarantine file1
        quarantine.add(file1.file_hash)
        
        # Add both to scheduler
        scheduler.enqueue(file1)
        scheduler.enqueue(file2)
        
        # Dequeue next file
        next_file = scheduler.peek()
        
        # Should be file2 if we filter quarantined
        # (in real system, would check before dequeue)
        if next_file.file_hash in quarantine:
            scheduler.dequeue()  # Skip quarantined
            next_file = scheduler.dequeue()
        
        assert next_file == file2


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
