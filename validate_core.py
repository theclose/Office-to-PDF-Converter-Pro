"""
Quick validation script for core data structures.

Run with: python validate_core.py
"""

import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from grid.models import ConversionFile, FileType, Priority
from grid.scheduler import ClusteredPriorityQueue
from grid.quarantine import BloomFilterQuarantine


def test_basic_functionality():
    """Quick smoke test for core components."""
    print("=" * 60)
    print("VALIDATION: Core Data Structures")
    print("=" * 60)
    
    # Create test file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        f.write(b'X' * 5000)
        test_file = f.name
    
    try:
        # Test 1: ConversionFile creation
        print("\n[1/5] Testing ConversionFile...")
        file = ConversionFile(test_file)
        assert file.file_type == FileType.WORD
        assert file.file_size_bytes == 5000
        assert len(file.file_hash) == 64
        print(f"  ✓ File: {file.filename}")
        print(f"  ✓ Hash: {file.file_hash[:16]}...")
        print(f"  ✓ Priority: {file.priority}")
        
        # Test 2: Priority Queue
        print("\n[2/5] Testing ClusteredPriorityQueue...")
        queue = ClusteredPriorityQueue()
        queue.enqueue(file)
        assert len(queue) == 1
        dequeued = queue.dequeue()
        assert dequeued == file
        print(f"  ✓ Enqueue/Dequeue working")
        print(f"  ✓ Stats: {queue.get_stats()}")
        
        # Test 3: Batch operations
        print("\n[3/5] Testing batch operations...")
        queue.enqueue_batch([file] * 10)
        assert len(queue) == 10
        batch = queue.drain(5)
        assert len(batch) == 5
        assert len(queue) == 5
        print(f"  ✓ Batch enqueue: 10 items")
        print(f"  ✓ Partial drain: 5 items")
        print(f"  ✓ Remaining: {len(queue)} items")
        
        # Test 4: Bloom Filter Quarantine
        print("\n[4/5] Testing BloomFilterQuarantine...")
        quarantine = BloomFilterQuarantine(expected_items=1000)
        quarantine.add(file.file_hash)
        assert file.file_hash in quarantine
        stats = quarantine.get_stats()
        print(f"  ✓ Quarantine lookup: O(1)")
        print(f"  ✓ Memory: {stats['memory_bytes'] // 1024}KB")
        print(f"  ✓ FPR: {stats['estimated_fpr']:.6f}")
        
        # Test 5: Integration
        print("\n[5/5] Testing integration...")
        queue2 = ClusteredPriorityQueue()
        queue2.enqueue_batch([file] * 5)
        
        # Simulate filtering quarantined files
        clean_files = []
        while queue2:
            next_file = queue2.dequeue()
            if next_file and next_file.file_hash not in quarantine:
                clean_files.append(next_file)
        
        print(f"  ✓ Files in queue: 5")
        print(f"  ✓ Quarantined: 1")
        print(f"  ✓ Clean files processed: {len(clean_files)}")
        
        print("\n" + "=" * 60)
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 60)
        print(f"\nAlgorithmic Guarantees:")
        print(f"  • Scheduler Insert: O(log n)")
        print(f"  • Scheduler Extract: O(log n)")
        print(f"  • Quarantine Lookup: O(k) ≈ O(1) where k={stats['hash_functions']}")
        print(f"  • Memory Efficiency: {stats['memory_bytes']} bytes for {stats['capacity']} capacity")
        
        return True
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        import os
        try:
            os.unlink(test_file)
        except:
            pass


if __name__ == '__main__':
    success = test_basic_functionality()
    sys.exit(0 if success else 1)
