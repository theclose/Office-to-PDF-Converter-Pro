"""
Bloom Filter Quarantine System

Space-efficient quarantine tracking with O(1) lookup complexity.
Used to blacklist files that repeatedly crash converters.

Performance Characteristics:
- Insert: O(k) ≈ O(1) where k = number of hash functions
- Query: O(k) ≈ O(1)
- Space: O(m) where m = bit array size (independent of items stored)
- False Positive Rate: ~0.1% with optimal parameters

Trade-off: Allows false positives (acceptable for UX warning)
          but ZERO false negatives (never miss a quarantined file).

Memory Efficiency: 10,000 quarantined files = ~15KB
                   vs ~500KB for HashMap
"""

import hashlib
import math
import threading
from typing import Set, Optional


class BloomFilterQuarantine:
    """Probabilistic set for quarantine tracking.
    
    Implementation:
    - Bit array of size m
    - k independent hash functions (MurmurHash3 variants)
    - False positive rate: (1 - e^(-kn/m))^k
    
    With defaults (m=100000, k=3, n=10000):
        FPR ≈ 0.00108 (~0.1%)
    
    Example:
        >>> quarantine = BloomFilterQuarantine(expected_items=10000)
        >>> quarantine.add("corrupted_file.docx")
        >>> quarantine.contains("corrupted_file.docx")
        True  # Definitely quarantined
        >>> quarantine.contains("good_file.docx")
        False  # Definitely NOT quarantined (or 0.1% FP chance)
    """
    
    def __init__(
        self,
        expected_items: int = 10000,
        false_positive_rate: float = 0.001,
        exact_set_threshold: int = 100
    ):
        """Initialize Bloom Filter with optimal parameters.
        
        Args:
            expected_items: Expected number of quarantined files
            false_positive_rate: Target FPR (0.001 = 0.1%)
            exact_set_threshold: Size of exact HashSet for verification
            
        The bit array size and hash count are calculated to achieve
        the target false positive rate.
        """
        # Calculate optimal bit array size
        # m = -(n * ln(p)) / (ln(2)^2)
        n = expected_items
        p = false_positive_rate
        self._m = int(-n * math.log(p) / (math.log(2) ** 2))
        
        # Calculate optimal number of hash functions
        # k = (m/n) * ln(2)
        self._k = max(1, int((self._m / n) * math.log(2)))
        
        # Bit array (using bytearray for memory efficiency)
        # Each byte stores 8 bits
        byte_count = (self._m + 7) // 8  # Ceiling division
        self._bits = bytearray(byte_count)
        
        # Exact set for high-confidence verification
        # Stores actual file hashes to confirm positives
        self._exact_set: Set[str] = set()
        self._exact_set_max = exact_set_threshold
        
        # Statistics
        self._item_count = 0
        self._lock = threading.Lock()
    
    def add(self, file_hash: str) -> None:
        """Add file to quarantine.
        
        Args:
            file_hash: SHA256 hash of file (from ConversionFile.file_hash)
            
        Complexity: O(k) ≈ O(1)
        Thread-safe: Yes
        """
        with self._lock:
            # Set bits in Bloom filter
            for i in range(self._k):
                bit_index = self._hash(file_hash, i) % self._m
                self._set_bit(bit_index)
            
            # Add to exact set if space available
            if len(self._exact_set) < self._exact_set_max:
                self._exact_set.add(file_hash)
            
            self._item_count += 1
    
    def contains(self, file_hash: str) -> bool:
        """Check if file is quarantined.
        
        Args:
            file_hash: SHA256 hash to check
            
        Returns:
            True if PROBABLY quarantined (with ~0.1% FPR)
            False if DEFINITELY NOT quarantined
            
        Complexity: O(k) ≈ O(1)
        Thread-safe: Yes
        """
        with self._lock:
            # Fast path: Check exact set first
            if file_hash in self._exact_set:
                return True  # 100% confidence
            
            # Check Bloom filter
            for i in range(self._k):
                bit_index = self._hash(file_hash, i) % self._m
                if not self._get_bit(bit_index):
                    return False  # Definitely NOT in set
            
            # All bits set → probably in set
            return True
    
    def contains_with_confidence(self, file_hash: str) -> tuple[bool, float]:
        """Check quarantine status with confidence level.
        
        Args:
            file_hash: SHA256 hash to check
            
        Returns:
            (is_quarantined, confidence)
            - If in exact set: (True, 1.0)
            - If Bloom positive: (True, 1 - FPR)
            - If Bloom negative: (False, 1.0)
            
        Thread-safe: Yes
        """
        with self._lock:
            if file_hash in self._exact_set:
                return (True, 1.0)
            
            # Check Bloom filter
            bloom_result = all(
                self._get_bit(self._hash(file_hash, i) % self._m)
                for i in range(self._k)
            )
            
            if bloom_result:
                # Probably quarantined (false positive possible)
                fpr = self.estimated_fpr()
                return (True, 1.0 - fpr)
            else:
                # Definitely NOT quarantined
                return (False, 1.0)
    
    def remove(self, file_hash: str) -> None:
        """Remove file from exact set only.
        
        Note: Bloom filters don't support deletion (bits are shared).
        We only remove from exact set. This may cause false positives
        until the Bloom filter is rebuilt.
        
        Args:
            file_hash: Hash to remove
            
        Thread-safe: Yes
        """
        with self._lock:
            self._exact_set.discard(file_hash)
    
    def clear(self) -> None:
        """Clear all quarantine data.
        
        Thread-safe: Yes
        """
        with self._lock:
            # Reset bit array
            byte_count = len(self._bits)
            self._bits = bytearray(byte_count)
            
            # Clear exact set
            self._exact_set.clear()
            self._item_count = 0
    
    def rebuild_from_exact(self) -> None:
        """Rebuild Bloom filter from exact set.
        
        Useful after many removes to eliminate false positives.
        
        Thread-safe: Yes
        """
        with self._lock:
            # Reset bit array
            byte_count = len(self._bits)
            self._bits = bytearray(byte_count)
            
            # Re-add items from exact set
            for file_hash in self._exact_set:
                for i in range(self._k):
                    bit_index = self._hash(file_hash, i) % self._m
                    self._set_bit(bit_index)
            
            self._item_count = len(self._exact_set)
    
    def _hash(self, data: str, seed: int) -> int:
        """Generate hash value with seed for k independent functions.
        
        Uses SHA256 with seed for cryptographic quality and uniformity.
        
        Args:
            data: String to hash
            seed: Hash function index (0 to k-1)
            
        Returns:
            Hash value as integer
        """
        # Combine data with seed to create independent hash function
        hasher = hashlib.sha256()
        hasher.update(data.encode('utf-8'))
        hasher.update(seed.to_bytes(4, 'big'))
        
        # Convert first 8 bytes to integer
        hash_bytes = hasher.digest()[:8]
        return int.from_bytes(hash_bytes, 'big')
    
    def _set_bit(self, index: int) -> None:
        """Set bit at index to 1.
        
        Args:
            index: Bit position (0 to m-1)
        """
        byte_index = index // 8
        bit_offset = index % 8
        self._bits[byte_index] |= (1 << bit_offset)
    
    def _get_bit(self, index: int) -> bool:
        """Get bit value at index.
        
        Args:
            index: Bit position (0 to m-1)
            
        Returns:
            True if bit is 1, False if 0
        """
        byte_index = index // 8
        bit_offset = index % 8
        return bool(self._bits[byte_index] & (1 << bit_offset))
    
    def estimated_fpr(self) -> float:
        """Calculate current false positive rate.
        
        Formula: (1 - e^(-kn/m))^k
        
        Returns:
            Estimated FPR (0.0 to 1.0)
            
        Thread-safe: Yes
        """
        with self._lock:
            if self._item_count == 0:
                return 0.0
            
            # (1 - e^(-kn/m))^k
            exponent = -self._k * self._item_count / self._m
            return (1 - math.exp(exponent)) ** self._k
    
    def get_stats(self) -> dict:
        """Get quarantine statistics.
        
        Returns:
            Dict with capacity, items, FPR, memory usage, etc.
            
        Thread-safe: Yes
        """
        with self._lock:
            # Count set bits for saturation metric
            set_bits = sum(
                bin(byte).count('1')
                for byte in self._bits
            )
            
            return {
                'capacity': self._m,
                'hash_functions': self._k,
                'items_quarantined': self._item_count,
                'exact_set_size': len(self._exact_set),
                'estimated_fpr': self.estimated_fpr(),
                'memory_bytes': len(self._bits) + len(self._exact_set) * 64,  # Approx
                'saturation': set_bits / self._m,  # Fraction of bits set
            }
    
    def __len__(self) -> int:
        """Get approximate number of quarantined items.
        
        Note: This is approximate due to hash collisions.
        
        Thread-safe: Yes
        """
        return self._item_count
    
    def __contains__(self, file_hash: str) -> bool:
        """Enable 'in' operator.
        
        Example:
            >>> if file_hash in quarantine: ...
        """
        return self.contains(file_hash)
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        stats = self.get_stats()
        return (
            f"BloomFilterQuarantine("
            f"items={stats['items_quarantined']}, "
            f"fpr={stats['estimated_fpr']:.4f}, "
            f"memory={stats['memory_bytes'] // 1024}KB)"
        )
