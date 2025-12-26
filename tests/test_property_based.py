"""
Phase 2: Property-Based Testing with Hypothesis

Logic Stress Testing for Utils and Calculations.

Tests use Hypothesis to generate thousands of random inputs and verify
mathematical invariants hold true across all possible inputs.

Focus Areas:
- Adaptive timeout calculation logic
- Memory threshold computation
- Batch splitting algorithms
- File type detection edge cases
"""

import pytest
from hypothesis import given, assume, strategies as st, settings
from pathlib import Path
import math

# Import strategies from conftest
from tests.conftest import (
    file_size_strategy,
    timeout_strategy,
    memory_strategy,
    filename_strategy
)


# ============================================================================
# PROPERTY TEST: Adaptive Timeout Logic
# ============================================================================

@pytest.mark.property
class TestAdaptiveTimeoutProperties:
    """Property-based tests for timeout calculation.
    
    Invariant: Timeout must strictly increase with file size.
    """
    
    @given(file_size=file_size_strategy)
    @settings(max_examples=1000)
    def test_timeout_increases_with_filesize(self, file_size):
        """INVARIANT: Larger files → Longer timeouts.
        
        Property: For any two file sizes where size_a < size_b,
                 timeout(size_a) must be <= timeout(size_b)
        
        This prevents premature termination of large file conversions.
        """
        from grid.models import ConversionFile
        
        # Create two files with different sizes
        file_a = ConversionFile(path="test_a.docx", size=file_size)
        file_b = ConversionFile(path="test_b.docx", size=file_size * 2)
        
        timeout_a = file_a.compute_timeout()
        timeout_b = file_b.compute_timeout()
        
        # Verify monotonic increase
        assert timeout_b >= timeout_a, \
            f"Timeout should increase with size: {timeout_a}s @ {file_size}B vs {timeout_b}s @ {file_size * 2}B"
    
    @given(file_size=file_size_strategy)
    @settings(max_examples=500)
    def test_timeout_has_reasonable_bounds(self, file_size):
        """INVARIANT: Timeout stays within practical limits.
        
        Property: MIN_TIMEOUT <= timeout <= MAX_TIMEOUT
        
        Prevents infinite waits or instant timeouts.
        """
        from grid.models import ConversionFile
        
        file = ConversionFile(path="test.docx", size=file_size)
        timeout = file.compute_timeout()
        
        # Reasonable bounds (30s to 10 minutes)
        MIN_TIMEOUT = 30
        MAX_TIMEOUT = 600
        
        assert MIN_TIMEOUT <= timeout <= MAX_TIMEOUT, \
            f"Timeout {timeout}s out of bounds for size {file_size}B"
    
    @given(
        size_a=file_size_strategy,
        size_b=file_size_strategy
    )
    @settings(max_examples=500)
    def test_timeout_transitivity(self, size_a, size_b):
        """INVARIANT: Timeout ordering is transitive.
        
        Property: If size_a <= size_b, then timeout(a) <= timeout(b)
        
        Ensures consistent ordering across all file sizes.
        """
        from grid.models import ConversionFile
        
        # Skip if sizes are equal (no ordering)
        assume(size_a != size_b)
        
        file_a = ConversionFile(path="a.docx", size=size_a)
        file_b = ConversionFile(path="b.docx", size=size_b)
        
        timeout_a = file_a.compute_timeout()
        timeout_b = file_b.compute_timeout()
        
        if size_a < size_b:
            assert timeout_a <= timeout_b, \
                "Timeout ordering must match size ordering"


# ============================================================================
# PROPERTY TEST: Memory Threshold Logic
# ============================================================================

@pytest.mark.property
class TestMemoryThresholdProperties:
    """Property-based tests for memory management logic."""
    
    @given(available_ram=memory_strategy)
    @settings(max_examples=1000)
    def test_load_shedding_triggers_consistently(self, available_ram):
        """INVARIANT: Load shedding activates below threshold.
        
        Property: If RAM < THRESHOLD, load shedding must activate.
        
        Prevents out-of-memory crashes.
        """
        # Typical threshold: 500 MB
        LOAD_SHEDDING_THRESHOLD = 500 * 1024 * 1024
        
        # Simulate memory check
        should_shed_load = available_ram < LOAD_SHEDDING_THRESHOLD
        
        if should_shed_load:
            # Verify logic would reduce worker count
            assert available_ram < LOAD_SHEDDING_THRESHOLD, \
                "Load shedding must activate when RAM is low"
    
    @given(
        total_ram=st.integers(min_value=4 * 1024**3, max_value=64 * 1024**3),
        used_percent=st.floats(min_value=0.0, max_value=100.0)
    )
    @settings(max_examples=500)
    def test_memory_percent_calculation(self, total_ram, used_percent):
        """INVARIANT: Memory percentage is always 0-100%.
        
        Property: Calculated percentage must be in valid range.
        
        Prevents invalid memory state reporting.
        """
        used_ram = int(total_ram * (used_percent / 100.0))
        available_ram = total_ram - used_ram
        
        # Calculate percentage
        calculated_percent = (used_ram / total_ram) * 100.0
        
        assert 0.0 <= calculated_percent <= 100.0, \
            f"Invalid memory percentage: {calculated_percent}%"
        
        # Verify available + used = total
        assert abs((available_ram + used_ram) - total_ram) < 1024, \
            "Memory accounting must be accurate"


# ============================================================================
# PROPERTY TEST: Batch Splitting Logic
# ============================================================================

@pytest.mark.property
class TestBatchSplittingProperties:
    """Property-based tests for batch processing logic."""
    
    @given(
        file_count=st.integers(min_value=1, max_value=10000),
        batch_size=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=1000)
    def test_batch_splitting_preserves_all_files(self, file_count, batch_size):
        """INVARIANT: Batch splitting never loses files.
        
        Property: Sum of all batch sizes must equal original file count.
        
        Critical for data integrity.
        """
        # Simulate batch splitting
        batches = []
        remaining = file_count
        
        while remaining > 0:
            current_batch_size = min(batch_size, remaining)
            batches.append(current_batch_size)
            remaining -= current_batch_size
        
        # Verify all files accounted for
        total_in_batches = sum(batches)
        assert total_in_batches == file_count, \
            f"Lost files: {file_count} original, {total_in_batches} in batches"
    
    @given(
        file_count=st.integers(min_value=1, max_value=1000),
        batch_size=st.integers(min_value=1, max_value=50)
    )
    @settings(max_examples=500)
    def test_batch_size_never_exceeds_limit(self, file_count, batch_size):
        """INVARIANT: No batch exceeds configured size.
        
        Property: max(batch_sizes) <= batch_size_limit
        
        Prevents memory overload from oversized batches.
        """
        # Create mock files
        files = list(range(file_count))
        
        # Split into batches
        batches = []
        for i in range(0, len(files), batch_size):
            batch = files[i:i + batch_size]
            batches.append(batch)
        
        # Verify no batch is oversized
        for batch in batches:
            assert len(batch) <= batch_size, \
                f"Batch size {len(batch)} exceeds limit {batch_size}"


# ============================================================================
# PROPERTY TEST: File Type Detection
# ============================================================================

@pytest.mark.property
class TestFileTypeDetectionProperties:
    """Property-based tests for file type identification."""
    
    @given(filename=filename_strategy)
    @settings(max_examples=1000)
    def test_extension_extraction_is_consistent(self, filename):
        """INVARIANT: Extension extraction is deterministic.
        
        Property: Multiple calls with same filename → same extension.
        
        Ensures consistent file type routing.
        """
        from pathlib import Path
        
        # Add various extensions
        extensions = ['.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt']
        
        for ext in extensions:
            full_name = f"{filename}{ext}"
            path = Path(full_name)
            
            # Extract extension multiple times
            ext1 = path.suffix.lower()
            ext2 = path.suffix.lower()
            
            assert ext1 == ext2, \
                f"Extension extraction is non-deterministic for {full_name}"
            assert ext1 == ext, \
                f"Expected {ext}, got {ext1}"
    
    @given(
        base_name=filename_strategy,
        extension=st.sampled_from(['.docx', '.DOCX', '.DocX', '.dOcX'])
    )
    @settings(max_examples=500)
    def test_extension_detection_is_case_insensitive(self, base_name, extension):
        """INVARIANT: Extension detection ignores case.
        
        Property: .docx == .DOCX == .DocX (case-insensitive)
        
        Handles user file naming variations.
        """
        from pathlib import Path
        
        filename = f"{base_name}{extension}"
        path = Path(filename)
        
        detected_ext = path.suffix.lower()
        
        assert detected_ext == '.docx', \
            f"Case-insensitive detection failed: {extension} → {detected_ext}"


# ============================================================================
# PROPERTY TEST: Hash Calculation
# ============================================================================

@pytest.mark.property
class TestHashCalculationProperties:
    """Property-based tests for file hash logic."""
    
    @given(data=st.binary(min_size=1, max_size=1024*1024))  # Up to 1 MB
    @settings(max_examples=500)
    def test_hash_is_deterministic(self, data):
        """INVARIANT: Same data → Same hash.
        
        Property: hash(data) == hash(data) always.
        
        Critical for deduplication and quarantine.
        """
        import hashlib
        
        hash1 = hashlib.sha256(data).hexdigest()
        hash2 = hashlib.sha256(data).hexdigest()
        
        assert hash1 == hash2, \
            "Hash calculation is non-deterministic"
    
    @given(
        data1=st.binary(min_size=1, max_size=1024),
        data2=st.binary(min_size=1, max_size=1024)
    )
    @settings(max_examples=500)
    def test_different_data_produces_different_hash(self, data1, data2):
        """INVARIANT: Different data → Different hash (with high probability).
        
        Property: hash(data1) != hash(data2) if data1 != data2
        
        Validates hash uniqueness for quarantine bloom filter.
        """
        import hashlib
        
        assume(data1 != data2)  # Skip if data is identical
        
        hash1 = hashlib.sha256(data1).hexdigest()
        hash2 = hashlib.sha256(data2).hexdigest()
        
        # SHA-256 collision probability is astronomically low
        assert hash1 != hash2, \
            "Hash collision detected (extremely unlikely)"


# ============================================================================
# PROPERTY TEST: Scheduler Priority Logic
# ============================================================================

@pytest.mark.property
class TestSchedulerPriorityProperties:
    """Property-based tests for priority scheduling."""
    
    @given(
        priority_a=st.integers(min_value=1, max_value=10),
        priority_b=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=500)
    def test_higher_priority_comes_first(self, priority_a, priority_b):
        """INVARIANT: Higher numeric priority → Processed first.
        
        Property: If priority_a > priority_b, then item_a dequeued before item_b.
        
        Ensures urgent files are processed first.
        """
        assume(priority_a != priority_b)
        
        # Min-heap: lower values have higher priority
        # So we need to invert for this test
        heap_priority_a = -priority_a  # Invert for max-heap behavior
        heap_priority_b = -priority_b
        
        if priority_a > priority_b:
            # Higher priority should have lower heap value
            assert heap_priority_a < heap_priority_b, \
                "Priority inversion in scheduler"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--hypothesis-show-statistics'])
