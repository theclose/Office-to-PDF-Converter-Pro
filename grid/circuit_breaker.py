"""
Circuit Breaker Coordinator - Cross-Worker Failure Tracking

Aggregates circuit breaker states across all workers to implement
grid-wide quarantine decisions.

Problem:
- Each worker has its own circuit breaker state
- File might fail on Worker1, succeed on Worker2
- Need centralized decision: "should ANY worker attempt this file?"

Solution:
- Central registry of circuit breaker states by file_hash
- Workers report failures to coordinator
- Coordinator makes quarantine decisions
- Bloom filter for fast O(1) quarantine checks

State Synchronization:
┌──────────┐    Failure     ┌────────────────┐
│ Worker 1 │───────────────▶│   Coordinator  │
└──────────┘                │                │
┌──────────┐    Failure     │ • Aggregate CB │
│ Worker 2 │───────────────▶│   states       │
└──────────┘                │ • Update Bloom │
┌──────────┐   Query OK?    │   filter       │
│ Worker 3 │◀───────────────│ • Decide       │
└──────────┘     No (OPEN)  │   quarantine   │
                            └────────────────┘
"""

import time
import logging
import threading
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

from grid.models import ConversionFile, CircuitBreakerState
from grid.quarantine import BloomFilterQuarantine


logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker pattern."""
    failure_threshold: int = 3  # Failures before OPEN
    cooldown_seconds: float = 30.0  # Wait before HALF_OPEN
    success_threshold: int = 2  # Successes to CLOSE circuit
    timeout_window: float = 60.0  # Rolling window for failures


class CircuitBreakerCoordinator:
    """Centralized circuit breaker management across workers.
    
    Features:
    - Aggregates failure reports from all workers
    - Maintains global circuit breaker state per file
    - Decides when to quarantine files
    - Provides O(1) quarantine lookups via Bloom filter
    - Thread-safe for concurrent worker access
    
    Example:
        >>> coordinator = CircuitBreakerCoordinator()
        >>> 
        >>> # Worker reports failure
        >>> coordinator.record_failure(file)
        >>> 
        >>> # Check if should attempt
        >>> if coordinator.should_allow_attempt(file):
        ...     # OK to try
        ...     result = convert(file)
        ...     if result.success:
        ...         coordinator.record_success(file)
    """
    
    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        quarantine: Optional[BloomFilterQuarantine] = None
    ):
        """Initialize coordinator.
        
        Args:
            config: Circuit breaker configuration
            quarantine: Bloom filter for quarantine (creates new if None)
        """
        self.config = config or CircuitBreakerConfig()
        self.quarantine = quarantine or BloomFilterQuarantine(expected_items=10000)
        
        # Circuit breaker states by file hash
        self._circuits: Dict[str, CircuitBreakerState] = {}
        self._lock = threading.Lock()
        
        # Statistics
        self.total_failures = 0
        self.total_successes = 0
        self.total_quarantined = 0
    
    def should_allow_attempt(self, file: ConversionFile) -> Tuple[bool, str]:
        """Check if file should be allowed for conversion.
        
        Args:
            file: ConversionFile to check
            
        Returns:
            (should_allow, reason)
            - (True, "OK") if allowed
            - (False, "Circuit OPEN") if circuit breaker open
            - (False, "Quarantined") if in quarantine
        """
        with self._lock:
            # Fast path: Check Bloom filter
            if file.file_hash in self.quarantine:
                return (False, f"Quarantined (failed {self.config.failure_threshold}+ times)")
            
            # Check circuit breaker state
            circuit = self._circuits.get(file.file_hash)
            if circuit is None:
                # No history, allow attempt
                return (True, "OK")
            
            current_time = time.time()
            if circuit.should_allow_attempt(current_time):
                return (True, f"OK (state: {circuit.state})")
            else:
                # Circuit OPEN
                cooldown_remaining = circuit.cooldown_until - current_time
                return (
                    False,
                    f"Circuit OPEN (cooldown: {cooldown_remaining:.1f}s remaining)"
                )
    
    def record_failure(self, file: ConversionFile, error: str = ""):
        """Record a conversion failure.
        
        Args:
            file: ConversionFile that failed
            error: Error message (optional)
        """
        with self._lock:
            # Get or create circuit state
            circuit = self._circuits.get(
                file.file_hash,
                CircuitBreakerState(file_hash=file.file_hash)
            )
            
            # Record failure
            current_time = time.time()
            circuit.record_failure(
                current_time,
                threshold=self.config.failure_threshold,
                cooldown=self.config.cooldown_seconds
            )
            
            # Update registry
            self._circuits[file.file_hash] = circuit
            self.total_failures += 1
            
            # Check if should quarantine
            if circuit.state == 'OPEN' and file.file_hash not in self.quarantine:
                logger.warning(
                    f"Quarantining file {file.filename} "
                    f"(failed {circuit.failure_count} times)"
                )
                self.quarantine.add(file.file_hash)
                self.total_quarantined += 1
    
    def record_success(self, file: ConversionFile):
        """Record a successful conversion.
        
        Args:
            file: ConversionFile that succeeded
        """
        with self._lock:
            circuit = self._circuits.get(file.file_hash)
            if circuit:
                circuit.record_success()
                self.total_successes += 1
                
                # If was in quarantine, it's now verified good
                # (user manually retried and it succeeded)
                if file.file_hash in self.quarantine:
                    logger.info(f"Removing {file.filename} from quarantine (manual retry succeeded)")
                    self.quarantine.remove(file.file_hash)
    
    def get_circuit_state(self, file: ConversionFile) -> Optional[CircuitBreakerState]:
        """Get circuit breaker state for file.
        
        Args:
            file: ConversionFile to query
            
        Returns:
            CircuitBreakerState or None if no history
        """
        with self._lock:
            return self._circuits.get(file.file_hash)
    
    def reset_circuit(self, file: ConversionFile):
        """Manually reset circuit breaker for file.
        
        Useful for user-initiated retries.
        
        Args:
            file: ConversionFile to reset
        """
        with self._lock:
            if file.file_hash in self._circuits:
                del self._circuits[file.file_hash]
            
            # Also remove from quarantine
            if file.file_hash in self.quarantine:
                self.quarantine.remove(file.file_hash)
                logger.info(f"Reset circuit and quarantine for {file.filename}")
    
    def get_stats(self) -> dict:
        """Get coordinator statistics.
        
        Returns:
            Dict with failure counts, quarantine size, circuit states, etc.
        """
        with self._lock:
            circuit_states = {
                'CLOSED': 0,
                'OPEN': 0,
                'HALF_OPEN': 0
            }
            
            for circuit in self._circuits.values():
                circuit_states[circuit.state] = circuit_states.get(circuit.state, 0) + 1
            
            return {
                'total_failures': self.total_failures,
                'total_successes': self.total_successes,
                'total_quarantined': self.total_quarantined,
                'circuit_states': circuit_states,
                'unique_files_tracked': len(self._circuits),
                'quarantine_stats': self.quarantine.get_stats(),
            }
    
    def cleanup_old_circuits(self, max_age_seconds: float = 3600.0):
        """Remove circuit breaker states for old files.
        
        Prevents unbounded memory growth.
        
        Args:
            max_age_seconds: Maximum age to keep (default 1 hour)
        """
        with self._lock:
            current_time = time.time()
            to_remove = []
            
            for file_hash, circuit in self._circuits.items():
                age = current_time - circuit.last_failure_time
                if age > max_age_seconds and circuit.state == 'CLOSED':
                    to_remove.append(file_hash)
            
            for file_hash in to_remove:
                del self._circuits[file_hash]
            
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} old circuit breaker states")
