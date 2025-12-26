"""
Conversion Grid Controller - High-Level Orchestration

Integrates all components into a unified conversion system:
- Scheduler: Clustered priority queue
- Worker Pool: Multi-process execution with hot spare
- Circuit Breaker: Failure tracking and quarantine
- Quarantine: Bloom filter for fast lookups

This is the primary interface for the conversion grid.

Example Usage:
    >>> from grid import ConversionGrid
    >>> 
    >>> # Create grid with 4 workers + hot spare
    >>> grid = ConversionGrid(num_workers=4, enable_hot_spare=True)
    >>> grid.start()
    >>> 
    >>> # Submit files
    >>> files = [ConversionFile(path) for path in file_paths]
    >>> grid.enqueue_batch(files)
    >>> 
    >>> # Monitor progress
    >>> while grid.is_active():
    ...     stats = grid.get_stats()
    ...     print(f"Progress: {stats['completed']}/{stats['total']}")
    ...     time.sleep(1)
    >>> 
    >>> # Shutdown
    >>> grid.shutdown()
"""

import logging
import time
import threading
from typing import List, Optional, Callable
from pathlib import Path

from grid.models import ConversionFile
from grid.scheduler import ClusteredPriorityQueue
from grid.worker import WorkerConfig
from grid.pool import WorkerPool, PoolConfig
from grid.circuit_breaker import CircuitBreakerCoordinator, CircuitBreakerConfig
from grid.quarantine import BloomFilterQuarantine


logger = logging.getLogger(__name__)


class ConversionGrid:
    """High-level controller for autonomous conversion grid.
    
    Combines all sub-systems into a cohesive conversion platform:
    - Smart scheduling (O(log n) heap with type clustering)
    - Parallel execution (multi-process worker pool)
    - Fault tolerance (circuit breaker + quarantine)
    - Zero-downtime (hot spare failover)
    - Self-healing (automatic worker recovery)
    
    Architecture:
    ┌─────────────────────────────────────────────────┐
    │              Conversion Grid                     │
    ├─────────────────────────────────────────────────┤
    │  Scheduler (Min-Heap)                           │
    │    ↓                                            │
    │  Circuit Breaker (Filter Quarantined)           │
    │    ↓                                            │
    │  Worker Pool (4 workers + 1 hot spare)          │
    │    ├─ Worker 1 (COM + Circuit Breaker)          │
    │    ├─ Worker 2 (COM + Circuit Breaker)          │
    │    ├─ Worker 3 (COM + Circuit Breaker)          │
    │    ├─ Worker 4 (COM + Circuit Breaker)          │
    │    └─ Hot Spare (Pre-warmed)                    │
    │    ↓                                            │
    │  Result Aggregator                              │
    └─────────────────────────────────────────────────┘
    """
    
    def __init__(
        self,
        num_workers: int = 4,
        enable_hot_spare: bool = True,
        on_file_complete: Optional[Callable] = None,
        on_file_error: Optional[Callable] = None,
        on_progress: Optional[Callable] = None
    ):
        """Initialize conversion grid (does not start workers).
        
        Args:
            num_workers: Number of active worker processes
            enable_hot_spare: Enable pre-warmed spare for failover
            on_file_complete: Callback(file, result) when file completes
            on_file_error: Callback(file, error) when file fails
            on_progress: Callback(completed, total, current_file) for progress
        """
        # Callbacks
        self.on_file_complete = on_file_complete
        self.on_file_error = on_file_error
        self.on_progress = on_progress
        
        # Core components
        self.scheduler = ClusteredPriorityQueue()
        self.quarantine = BloomFilterQuarantine(expected_items=10000)
        self.circuit_breaker = CircuitBreakerCoordinator(quarantine=self.quarantine)
        
        # Worker pool configuration
        pool_config = PoolConfig(
            num_workers=num_workers,
            enable_hot_spare=enable_hot_spare,
            worker_config=WorkerConfig(worker_id=0)  # Base config, ID assigned per worker
        )
        
        self.pool = WorkerPool(
            config=pool_config,
            on_result=self._handle_result,
            on_worker_death=self._handle_worker_death
        )
        
        # Dispatcher thread (Scheduler → Workers)
        self._dispatcher_thread = None
        self._stop_event = threading.Event()
        
        # Statistics
        self.total_enqueued = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_quarantined = 0
        
        # Timing
        self.start_time = 0.0
    
    def start(self):
        """Start the conversion grid."""
        logger.info("Starting Conversion Grid")
        
        # Start worker pool
        self.pool.start()
        
        # Start dispatcher
        self._start_dispatcher()
        
        self.start_time = time.time()
        logger.info("Conversion Grid started successfully")
    
    def enqueue(self, file: ConversionFile) -> bool:
        """Add file to conversion queue.
        
        Args:
            file: ConversionFile to convert
            
        Returns:
            True if enqueued, False if rejected (quarantined)
        """
        # Check circuit breaker
        should_allow, reason = self.circuit_breaker.should_allow_attempt(file)
        
        if not should_allow:
            logger.warning(f"Rejecting {file.filename}: {reason}")
            self.total_quarantined += 1
            
            # Notify error callback
            if self.on_file_error:
                try:
                    self.on_file_error(file, reason)
                except Exception as e:
                    logger.error(f"on_file_error callback failed: {e}")
            
            return False
        
        # Add to scheduler
        self.scheduler.enqueue(file)
        self.total_enqueued += 1
        
        logger.debug(f"Enqueued {file.filename} (priority: {file.priority})")
        return True
    
    def enqueue_batch(self, files: List[ConversionFile]) -> int:
        """Add multiple files to queue.
        
        Args:
            files: List of ConversionFiles
            
        Returns:
            Number of files successfully enqueued
        """
        enqueued = 0
        for file in files:
            if self.enqueue(file):
                enqueued += 1
        
        logger.info(f"Batch enqueued: {enqueued}/{len(files)} files")
        return enqueued
    
    def is_active(self) -> bool:
        """Check if grid is currently processing files.
        
        Returns:
            True if files are pending or in progress
        """
        return (
            len(self.scheduler) > 0 or
            self.pool.task_queue.qsize() > 0 or
            self.pool.result_queue.qsize() > 0
        )
    
    def wait_completion(self, timeout: Optional[float] = None):
        """Wait for all files to complete.
        
        Args:
            timeout: Maximum seconds to wait (None = infinite)
        """
        start_wait = time.time()
        
        while self.is_active():
            if timeout and (time.time() - start_wait) > timeout:
                logger.warning(f"wait_completion timed out after {timeout}s")
                break
            
            time.sleep(0.5)
        
        logger.info("All files completed")
    
    def get_stats(self) -> dict:
        """Get comprehensive grid statistics.
        
        Returns:
            Dict with scheduler, pool, circuit breaker, and overall stats
        """
        pool_stats = self.pool.get_stats()
        cb_stats = self.circuit_breaker.get_stats()
        scheduler_stats = self.scheduler.get_stats()
        
        uptime = time.time() - self.start_time if self.start_time > 0 else 0
        
        return {
            # Overall
            'state': pool_stats['state'],
            'uptime_seconds': uptime,
            'total_enqueued': self.total_enqueued,
            'total_completed': self.total_completed,
            'total_failed': self.total_failed,
            'total_quarantined': self.total_quarantined,
            'success_rate': (
                (self.total_completed / max(1, self.total_completed + self.total_failed)) * 100
            ),
            
            # Scheduler
            'scheduler': {
                'pending': scheduler_stats['current_size'],
                'cluster_distribution': scheduler_stats['cluster_distribution'],
            },
            
            # Worker Pool
            'pool': {
                'active_workers': pool_stats['active_workers'],
                'hot_spare_ready': pool_stats['hot_spare_ready'],
                'tasks_in_flight': pool_stats['pending_tasks'],
            },
            
            # Circuit Breaker
            'circuit_breaker': {
                'failures': cb_stats['total_failures'],
                'successes': cb_stats['total_successes'],
                'quarantined': cb_stats['total_quarantined'],
                'circuit_states': cb_stats['circuit_states'],
            },
            
            # Quarantine
            'quarantine': cb_stats['quarantine_stats'],
        }
    
    def shutdown(self, timeout: float = 30.0):
        """Shutdown grid gracefully.
        
        Args:
            timeout: Maximum seconds to wait
        """
        logger.info("Shutting down Conversion Grid")
        
        # Stop dispatcher
        self._stop_event.set()
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=5.0)
        
        # Shutdown worker pool
        self.pool.shutdown(timeout=timeout)
        
        logger.info(
            f"Grid shutdown complete. "
            f"Processed: {self.total_completed}, "
            f"Failed: {self.total_failed}, "
            f"Quarantined: {self.total_quarantined}"
        )
    
    # ========================================================================
    # INTERNAL: Dispatcher
    # ========================================================================
    
    def _start_dispatcher(self):
        """Start dispatcher thread (Scheduler → Worker Pool)."""
        
        def dispatch_loop():
            logger.info("Dispatcher started")
            
            while not self._stop_event.is_set():
                try:
                    # Check if workers are ready for more tasks
                    if self.pool.task_queue.qsize() < self.pool.config.num_workers * 2:
                        # Get next file from scheduler
                        file = self.scheduler.dequeue()
                        
                        if file:
                            # Double-check circuit breaker (might have changed)
                            should_allow, reason = self.circuit_breaker.should_allow_attempt(file)
                            
                            if should_allow:
                                # Send to worker pool
                                self.pool.submit(file, timeout=5.0)
                            else:
                                # Quarantined since scheduling
                                logger.warning(f"Skipping quarantined file: {file.filename}")
                                self.total_quarantined += 1
                        else:
                            # No files in scheduler, sleep
                            time.sleep(0.1)
                    else:
                        # Workers busy, wait
                        time.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"Dispatcher error: {e}")
                    time.sleep(1.0)
            
            logger.info("Dispatcher stopped")
        
        self._dispatcher_thread = threading.Thread(
            target=dispatch_loop,
            daemon=True,
            name="Dispatcher"
        )
        self._dispatcher_thread.start()
    
    # ========================================================================
    # INTERNAL: Result Handling
    # ========================================================================
    
    def _handle_result(self, result: dict):
        """Process result from worker.
        
        Args:
            result: Dict with file, status, output_path, error, duration
        """
        file = result['file']
        status = result['status']
        
        if status == 'completed':
            # Success
            self.total_completed += 1
            self.circuit_breaker.record_success(file)
            
            logger.info(
                f"Completed: {file.filename} "
                f"({result['duration']:.2f}s)"
            )
            
            # Callback
            if self.on_file_complete:
                try:
                    self.on_file_complete(file, result)
                except Exception as e:
                    logger.error(f"on_file_complete callback failed: {e}")
        
        else:
            # Failure
            self.total_failed += 1
            error = result.get('error', 'Unknown error')
            self.circuit_breaker.record_failure(file, error)
            
            logger.error(f"Failed: {file.filename} - {error}")
            
            # Callback
            if self.on_file_error:
                try:
                    self.on_file_error(file, error)
                except Exception as e:
                    logger.error(f"on_file_error callback failed: {e}")
        
        # Progress callback
        if self.on_progress:
            try:
                total = self.total_completed + self.total_failed
                self.on_progress(self.total_completed, total, file.filename)
            except Exception as e:
                logger.error(f"on_progress callback failed: {e}")
    
    def _handle_worker_death(self, worker_id: int):
        """Handle worker process death.
        
        Args:
            worker_id: ID of dead worker
        """
        logger.error(f"Worker {worker_id} died - hot spare will take over")
        
        # Statistics are already updated by pool
        # This is just for additional logging/metrics
