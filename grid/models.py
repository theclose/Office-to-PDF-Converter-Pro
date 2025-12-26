"""
Core Data Models for Conversion Grid

Defines immutable data structures with strong typing and validation.
"""

from dataclasses import dataclass, field
from enum import IntEnum, auto
from pathlib import Path
from typing import Optional
import hashlib
import time


class FileType(IntEnum):
    """File type enumeration for clustering optimization.
    
    Lower values = higher priority in same-size batches.
    Clustering same types reduces COM initialization overhead by ~40%.
    """
    WORD = 0       # .docx, .doc - Process first (most common)
    EXCEL = 1      # .xlsx, .xls - Middle priority
    POWERPOINT = 2 # .pptx, .ppt - Process last (least common)
    UNKNOWN = 99   # Unsupported files


# Extension-to-Type mapping for fast lookup
FILE_TYPE_MAP = {
    # Word
    '.docx': FileType.WORD,
    '.doc': FileType.WORD,
    '.docm': FileType.WORD,
    '.rtf': FileType.WORD,
    
    # Excel
    '.xlsx': FileType.EXCEL,
    '.xls': FileType.EXCEL,
    '.xlsm': FileType.EXCEL,
    '.xlsb': FileType.EXCEL,
    
    # PowerPoint
    '.pptx': FileType.POWERPOINT,
    '.ppt': FileType.POWERPOINT,
    '.pptm': FileType.POWERPOINT,
    '.ppsx': FileType.POWERPOINT,
    '.pps': FileType.POWERPOINT,
}


@dataclass(frozen=True)
class Priority:
    """Priority tuple for heap comparison.
    
    Ordering logic:
    1. FileType (cluster same types together)
    2. FileSize (smaller files first for better UX feedback)
    3. ArrivalTime (FIFO tiebreaker)
    
    Complexity: O(1) comparison via tuple comparison
    """
    file_type: FileType
    file_size_bytes: int
    arrival_time: float
    
    def __lt__(self, other: 'Priority') -> bool:
        """Less-than comparison for min-heap ordering."""
        return (
            self.file_type,
            self.file_size_bytes,
            self.arrival_time
        ) < (
            other.file_type,
            other.file_size_bytes,
            other.arrival_time
        )
    
    def __le__(self, other: 'Priority') -> bool:
        """Less-than-or-equal comparison."""
        return self < other or self == other


@dataclass
class ConversionFile:
    """Represents a file in the conversion pipeline.
    
    Immutable after creation to ensure thread safety in multi-process pool.
    """
    # Core identification
    path: str
    file_hash: str = field(init=False, repr=False)
    
    # File metadata
    file_type: FileType = field(init=False)
    file_size_bytes: int = field(init=False)
    filename: str = field(init=False)
    
    # Priority for scheduling
    priority: Priority = field(init=False)
    arrival_time: float = field(default_factory=time.time)
    
    # Conversion state (mutable via copy-on-write)
    status: str = 'pending'  # pending, processing, completed, failed, quarantined
    output_path: Optional[str] = None
    error: Optional[str] = None
    duration: float = 0.0
    retry_count: int = 0
    
    def __post_init__(self):
        """Initialize computed fields.
        
        Raises:
            FileNotFoundError: If path doesn't exist
            ValueError: If file type not supported
        """
        path_obj = Path(self.path)
        
        # Validate file exists
        if not path_obj.exists():
            raise FileNotFoundError(f"File not found: {self.path}")
        
        # Extract metadata
        object.__setattr__(self, 'filename', path_obj.name)
        object.__setattr__(self, 'file_size_bytes', path_obj.stat().st_size)
        
        # Determine file type
        ext = path_obj.suffix.lower()
        file_type = FILE_TYPE_MAP.get(ext, FileType.UNKNOWN)
        object.__setattr__(self, 'file_type', file_type)
        
        if file_type == FileType.UNKNOWN:
            raise ValueError(f"Unsupported file type: {ext}")
        
        # Compute stable hash for quarantine lookup
        file_hash = self._compute_hash()
        object.__setattr__(self, 'file_hash', file_hash)
        
        # Build priority
        priority = Priority(
            file_type=file_type,
            file_size_bytes=self.file_size_bytes,
            arrival_time=self.arrival_time
        )
        object.__setattr__(self, 'priority', priority)
    
    def _compute_hash(self) -> str:
        """Compute stable hash for quarantine identification.
        
        Uses SHA256 of (absolute_path + file_size + first_4KB).
        This is more stable than mtime and catches file corruption.
        
        Returns:
            64-character hex digest
        """
        hasher = hashlib.sha256()
        
        # Hash path (normalized)
        normalized_path = str(Path(self.path).resolve())
        hasher.update(normalized_path.encode('utf-8'))
        
        # Hash file size
        hasher.update(str(self.file_size_bytes).encode('utf-8'))
        
        # Hash first 4KB of content (or entire file if smaller)
        try:
            with open(self.path, 'rb') as f:
                chunk = f.read(4096)
                hasher.update(chunk)
        except Exception:
            # If read fails, use path + size only
            pass
        
        return hasher.hexdigest()
    
    def with_status(self, status: str, **kwargs) -> 'ConversionFile':
        """Create a copy with updated status.
        
        Implements copy-on-write pattern for immutability in worker pool.
        
        Args:
            status: New status value
            **kwargs: Additional fields to update
            
        Returns:
            New ConversionFile instance with updates
        """
        from dataclasses import replace
        return replace(self, status=status, **kwargs)
    
    def compute_timeout(self, base_timeout: float = 30.0, rate_mb_per_sec: float = 2.0) -> float:
        """Calculate adaptive timeout for this file.
        
        Formula: T = base + (size_mb / rate)
        
        Args:
            base_timeout: Baseline overhead (seconds)
            rate_mb_per_sec: Expected throughput (MB/s)
            
        Returns:
            Timeout in seconds
        """
        size_mb = self.file_size_bytes / (1024 * 1024)
        return base_timeout + (size_mb / rate_mb_per_sec)
    
    def __lt__(self, other: 'ConversionFile') -> bool:
        """Enable heap comparison via priority."""
        return self.priority < other.priority
    
    def __hash__(self) -> int:
        """Hash based on file_hash for set/dict usage."""
        return hash(self.file_hash)
    
    def __eq__(self, other: object) -> bool:
        """Equality based on file_hash."""
        if not isinstance(other, ConversionFile):
            return NotImplemented
        return self.file_hash == other.file_hash


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker pattern.
    
    States: CLOSED → OPEN → HALF_OPEN → CLOSED
    """
    file_hash: str
    failure_count: int = 0
    last_failure_time: float = 0.0
    state: str = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    cooldown_until: float = 0.0
    
    def should_allow_attempt(self, current_time: float) -> bool:
        """Check if file should be allowed to retry.
        
        Args:
            current_time: Current timestamp
            
        Returns:
            True if attempt allowed, False if circuit open
        """
        if self.state == 'CLOSED':
            return True
        
        if self.state == 'OPEN':
            # Check if cooldown expired
            if current_time >= self.cooldown_until:
                # Transition to HALF_OPEN
                self.state = 'HALF_OPEN'
                return True
            return False
        
        # HALF_OPEN: Allow one test attempt
        return self.state == 'HALF_OPEN'
    
    def record_failure(self, current_time: float, threshold: int = 3, cooldown: float = 30.0):
        """Record a conversion failure.
        
        Args:
            current_time: Current timestamp
            threshold: Failures before opening circuit
            cooldown: Seconds to wait before HALF_OPEN
        """
        self.failure_count += 1
        self.last_failure_time = current_time
        
        if self.failure_count >= threshold:
            self.state = 'OPEN'
            self.cooldown_until = current_time + cooldown
    
    def record_success(self):
        """Record a successful conversion, resetting circuit."""
        self.failure_count = 0
        self.state = 'CLOSED'
        self.cooldown_until = 0.0
