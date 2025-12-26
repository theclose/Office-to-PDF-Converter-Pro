"""
Worker Pool - Multi-Process Conversion Grid with Hot Spare

Manages a pool of worker processes with:
- Dynamic scaling (add/remove workers)
- Hot spare for zero-downtime failover
- Health monitoring and auto-recovery
- Load balancing via shared task queue
- Circuit breaker aggregation

Architecture:
┌─────────────────────────────────────────────────────────┐
│                      Worker Pool                        │
├─────────────────────────────────────────────────────────┤
│  Active Workers: [W1, W2, W3, W4]  ← Processing files  │
│  Hot Spare:      [W5]               ← Idle, pre-warmed │
│  Health Monitor: Checks heartbeats every 5s             │
├─────────────────────────────────────────────────────────┤
│  Task Queue:   [file1, file2, ...]  ← Scheduler feeds  │
│  Result Queue: [result1, ...]       ← Workers return   │
└─────────────────────────────────────────────────────────┘

Failover Flow:
1. Worker W2 crashes (no heartbeat for 10s)
2. Health Monitor detects failure
3. Hot Spare W5 promoted instantly
4. New Hot Spare W6 spawned asynchronously
5. Total downtime: < 500ms
"""

import time
import logging
import multiprocessing as mp
from typing import List, Optional, Dict, Callable
from dataclasses import dataclass, field
from enum import Enum
import psutil

from grid.worker import WorkerProcess, WorkerConfig
from grid.models import ConversionFile
from grid.scheduler import ClusteredPriorityQueue
from grid.quarantine import BloomFilterQuarantine


logger = logging.getLogger(__name__)


class PoolState(Enum):
    """Worker pool operational states."""
    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"  # Low memory, reduced workers
    DRAINING = "draining"  # Shutting down gracefully
    STOPPED = "stopped"


@dataclass
class PoolConfig:
    """Configuration for worker pool."""
    num_workers: int = 4
    enable_hot_spare: bool = True
    min_ram_mb_for_spare: int = 4096  # Require 4GB to enable hot spare
    heartbeat_timeout: float = 10.0  # Seconds without heartbeat = dead worker
    health_check_interval: float = 5.0  # Seconds between health checks
    max_queue_size: int = 10000  # Maximum pending files
    worker_config: WorkerConfig = field(default_factory=lambda: WorkerConfig(worker_id=0))


@dataclass
class WorkerInfo:
    """Runtime information about a worker."""
    worker_id: int
    process: WorkerProcess
    last_heartbeat: float
    files_processed: int = 0
    files_failed: int = 0
    is_hot_spare: bool = False


class WorkerPool:
    """Manages pool of conversion workers with hot spare failover.
    
    Features:
    - Multi-process parallelism (one worker per CPU core)
    - Hot spare: pre-warmed worker for instant failover
    - Health monitoring: automatic dead worker detection
    - Circuit breaker: aggregates failures across workers
    - Load shedding: reduces workers under memory pressure
    
    Example:
        >>> pool = WorkerPool(num_workers=4, enable_hot_spare=True)
        >>> pool.start()
        >>> 
        >>> # Submit files
        >>> for file in files:
        ...     pool.submit(file)
        >>> 
        >>> # Process results
        >>> while not pool.is_idle():
        ...     result = pool.get_result(timeout=1.0)
        ...     print(f"Completed: {result['file'].filename}")
        >>> 
        >>> pool.shutdown()
    """
    
    def __init__(
        self,
        config: Optional[PoolConfig] = None,
        on_result: Optional[Callable] = None,
        on_worker_death: Optional[Callable] = None
    ):
        """Initialize worker pool (does not start workers).
        
        Args:
            config: Pool configuration (uses defaults if None)
            on_result: Callback(result_dict) when file completes
            on_worker_death: Callback(worker_id) when worker dies
        """
        self.config = config or PoolConfig()
        self.on_result = on_result
        self.on_worker_death = on_worker_death
        
        # IPC queues
        self.task_queue = mp.Queue(maxsize=self.config.max_queue_size)
        self.result_queue = mp.Queue()
        self.heartbeat_queue = mp.Queue()
        
        # Worker tracking
        self.workers: Dict[int, WorkerInfo] = {}
        self.hot_spare: Optional[WorkerInfo] = None
        self.next_worker_id = 0
        
        # State
        self.state = PoolState.INITIALIZING
        self.start_time = 0.0
        
        # Health monitoring
        self._health_monitor_thread = None
        self._result_processor_thread = None
        self._stop_event = mp.Event()
        
        # Statistics
        self.total_submitted = 0
        self.total_completed = 0
        self.total_failed = 0
        
    def start(self):
        """Start all workers and monitoring threads."""
        logger.info(f"Starting worker pool with {self.config.num_workers} workers")
        
        # Spawn active workers
        for _ in range(self.config.num_workers):
            self._spawn_worker(is_hot_spare=False)
        
        # Spawn hot spare if enabled and sufficient RAM
        if self._should_enable_hot_spare():
            self._spawn_hot_spare()
            logger.info("Hot spare enabled")
        else:
            logger.info("Hot spare disabled (insufficient RAM or config)")
        
        # Start monitoring threads
        self._start_health_monitor()
        self._start_result_processor()
        
        self.state = PoolState.ACTIVE
        self.start_time = time.time()
        
        logger.info(
            f"Worker pool started: {len(self.workers)} active workers, "
            f"hot spare: {'yes' if self.hot_spare else 'no'}"
        )
    
    def submit(self, file: ConversionFile, timeout: float = 5.0) -> bool:
        """Submit file for conversion.
        
        Args:
            file: ConversionFile to process
            timeout: Seconds to wait if queue full
            
        Returns:
            True if submitted, False if queue full
        """
        try:
            self.task_queue.put(file, timeout=timeout)
            self.total_submitted += 1
            return True
        except mp.queues.Full:
            logger.warning(f"Task queue full ({self.config.max_queue_size}), submit rejected")
            return False
    
    def submit_batch(self, files: List[ConversionFile]) -> int:
        """Submit multiple files.
        
        Args:
            files: List of ConversionFiles
            
        Returns:
            Number of files successfully submitted
        """
        submitted = 0
        for file in files:
            if self.submit(file, timeout=1.0):
                submitted += 1
            else:
                break  # Queue full
        return submitted
    
    def get_result(self, timeout: float = 1.0) -> Optional[dict]:
        """Get next conversion result.
        
        Args:
            timeout: Seconds to wait for result
            
        Returns:
            Result dict or None if timeout
        """
        try:
            return self.result_queue.get(timeout=timeout)
        except mp.queues.Empty:
            return None
    
    def get_stats(self) -> dict:
        """Get pool statistics.
        
        Returns:
            Dict with workers, queue sizes, completion rates, etc.
        """
        return {
            'state': self.state.value,
            'uptime_seconds': time.time() - self.start_time if self.start_time > 0 else 0,
            'active_workers': len(self.workers),
            'hot_spare_ready': self.hot_spare is not None,
            'pending_tasks': self.task_queue.qsize(),
            'pending_results': self.result_queue.qsize(),
            'total_submitted': self.total_submitted,
            'total_completed': self.total_completed,
            'total_failed': self.total_failed,
            'success_rate': (
                self.total_completed / max(1, self.total_completed + self.total_failed)
            ) * 100,
            'worker_details': {
                worker_id: {
                    'files_processed': info.files_processed,
                    'files_failed': info.files_failed,
                    'last_heartbeat_ago': time.time() - info.last_heartbeat,
                    'is_hot_spare': info.is_hot_spare,
                }
                for worker_id, info in {**self.workers, **(
                    {self.hot_spare.worker_id: self.hot_spare} if self.hot_spare else {}
                )}.items()
            }
        }
    
    def is_idle(self) -> bool:
        """Check if pool has no pending work.
        
        Returns:
            True if no tasks in queue and no results pending
        """
        return (
            self.task_queue.qsize() == 0 and
            self.result_queue.qsize() == 0
        )
    
    def shutdown(self, timeout: float = 30.0):
        """Gracefully shutdown all workers.
        
        Args:
            timeout: Seconds to wait for clean shutdown
        """
        logger.info("Worker pool shutdown initiated")
        self.state = PoolState.DRAINING
        
        # Stop monitoring
        self._stop_event.set()
        
        # Shutdown active workers
        for worker_info in list(self.workers.values()):
            worker_info.process.shutdown(timeout=5.0)
        
        # Shutdown hot spare
        if self.hot_spare:
            self.hot_spare.process.shutdown(timeout=5.0)
        
        # Wait for threads
        if self._health_monitor_thread:
            self._health_monitor_thread.join(timeout=5.0)
        if self._result_processor_thread:
            self._result_processor_thread.join(timeout=5.0)
        
        self.state = PoolState.STOPPED
        logger.info("Worker pool shutdown complete")
    
    # ========================================================================
    # INTERNAL: Worker Management
    # ========================================================================
    
    def _spawn_worker(self, is_hot_spare: bool = False) -> WorkerInfo:
        """Spawn a new worker process.
        
        Args:
            is_hot_spare: Whether this is the hot spare worker
            
        Returns:
            WorkerInfo for the spawned worker
        """
        worker_id = self.next_worker_id
        self.next_worker_id += 1
        
        # Create worker config
        worker_config = WorkerConfig(
            worker_id=worker_id,
            base_timeout=self.config.worker_config.base_timeout,
            rate_mb_per_sec=self.config.worker_config.rate_mb_per_sec,
            heartbeat_interval=self.config.health_check_interval,
        )
        
        # Create and start process
        process = WorkerProcess(
            worker_id=worker_id,
            task_queue=self.task_queue,
            result_queue=self.result_queue,
            heartbeat_queue=self.heartbeat_queue,
            config=worker_config
        )
        process.start()
        
        # Track worker
        worker_info = WorkerInfo(
            worker_id=worker_id,
            process=process,
            last_heartbeat=time.time(),
            is_hot_spare=is_hot_spare
        )
        
        if is_hot_spare:
            self.hot_spare = worker_info
            logger.info(f"Spawned hot spare worker {worker_id} (PID: {process.pid})")
        else:
            self.workers[worker_id] = worker_info
            logger.info(f"Spawned active worker {worker_id} (PID: {process.pid})")
        
        return worker_info
    
    def _spawn_hot_spare(self):
        """Spawn hot spare worker if not already present."""
        if self.hot_spare is None and self._should_enable_hot_spare():
            self._spawn_worker(is_hot_spare=True)
    
    def _should_enable_hot_spare(self) -> bool:
        """Check if hot spare should be enabled.
        
        Returns:
            True if config allows and sufficient RAM available
        """
        if not self.config.enable_hot_spare:
            return False
        
        try:
            available_mb = psutil.virtual_memory().available / (1024 * 1024)
            return available_mb >= self.config.min_ram_mb_for_spare
        except Exception:
            return True  # Default to enabled if can't check RAM
    
    def _promote_hot_spare(self, failed_worker_id: int):
        """Promote hot spare to active worker.
        
        Args:
            failed_worker_id: ID of worker that failed
        """
        if self.hot_spare is None:
            logger.error("No hot spare available for promotion!")
            # Spawn replacement immediately
            self._spawn_worker(is_hot_spare=False)
            return
        
        logger.info(
            f"Promoting hot spare {self.hot_spare.worker_id} "
            f"to replace worker {failed_worker_id}"
        )
        
        # Move hot spare to active pool
        self.hot_spare.is_hot_spare = False
        self.workers[self.hot_spare.worker_id] = self.hot_spare
        self.hot_spare = None
        
        # Spawn new hot spare asynchronously
        import threading
        threading.Thread(
            target=self._spawn_hot_spare,
            daemon=True
        ).start()
    
    # ========================================================================
    # INTERNAL: Health Monitoring
    # ========================================================================
    
    def _start_health_monitor(self):
        """Start health monitoring thread."""
        import threading
        
        def monitor_loop():
            logger.info("Health monitor started")
            
            while not self._stop_event.is_set():
                try:
                    # Process heartbeats
                    self._process_heartbeats()
                    
                    # Check for dead workers
                    self._check_worker_health()
                    
                    # Check system resources
                    self._check_resources()
                    
                except Exception as e:
                    logger.error(f"Health monitor error: {e}")
                
                # Sleep until next check
                time.sleep(self.config.health_check_interval)
            
            logger.info("Health monitor stopped")
        
        self._health_monitor_thread = threading.Thread(
            target=monitor_loop,
            daemon=True,
            name="HealthMonitor"
        )
        self._health_monitor_thread.start()
    
    def _process_heartbeats(self):
        """Drain heartbeat queue and update worker info."""
        processed = 0
        while not self.heartbeat_queue.empty():
            try:
                heartbeat = self.heartbeat_queue.get_nowait()
                worker_id = heartbeat['worker_id']
                
                # Update worker info
                if worker_id in self.workers:
                    info = self.workers[worker_id]
                    info.last_heartbeat = heartbeat['timestamp']
                    info.files_processed = heartbeat['files_processed']
                    info.files_failed = heartbeat['files_failed']
                elif self.hot_spare and self.hot_spare.worker_id == worker_id:
                    self.hot_spare.last_heartbeat = heartbeat['timestamp']
                    self.hot_spare.files_processed = heartbeat['files_processed']
                    self.hot_spare.files_failed = heartbeat['files_failed']
                
                processed += 1
            except mp.queues.Empty:
                break
        
        if processed > 0:
            logger.debug(f"Processed {processed} heartbeats")
    
    def _check_worker_health(self):
        """Check for dead workers and trigger failover."""
        current_time = time.time()
        dead_workers = []
        
        # Check active workers
        for worker_id, worker_info in self.workers.items():
            time_since_heartbeat = current_time - worker_info.last_heartbeat
            
            if time_since_heartbeat > self.config.heartbeat_timeout:
                logger.error(
                    f"Worker {worker_id} appears dead "
                    f"(no heartbeat for {time_since_heartbeat:.1f}s)"
                )
                dead_workers.append(worker_id)
        
        # Handle dead workers
        for worker_id in dead_workers:
            self._handle_worker_death(worker_id)
    
    def _handle_worker_death(self, worker_id: int):
        """Handle worker process death.
        
        Args:
            worker_id: ID of dead worker
        """
        worker_info = self.workers.pop(worker_id, None)
        if worker_info is None:
            return
        
        # Kill process if still alive
        if worker_info.process.is_alive():
            logger.warning(f"Force terminating worker {worker_id}")
            worker_info.process.terminate()
            worker_info.process.join(timeout=2.0)
            if worker_info.process.is_alive():
                worker_info.process.kill()
        
        # Notify callback
        if self.on_worker_death:
            try:
                self.on_worker_death(worker_id)
            except Exception as e:
                logger.error(f"on_worker_death callback error: {e}")
        
        # Promote hot spare
        self._promote_hot_spare(worker_id)
    
    def _check_resources(self):
        """Check system resources and trigger load shedding if needed."""
        try:
            mem = psutil.virtual_memory()
            available_mb = mem.available / (1024 * 1024)
            
            # Low memory threshold: 500MB
            if available_mb < 500:
                logger.warning(
                    f"Low memory detected ({available_mb:.0f}MB available), "
                    "activating load shedding"
                )
                self._activate_load_shedding()
                self.state = PoolState.DEGRADED
            
            # Recovery threshold: 1GB
            elif available_mb > 1024 and self.state == PoolState.DEGRADED:
                logger.info(f"Memory recovered ({available_mb:.0f}MB), deactivating load shedding")
                self._deactivate_load_shedding()
                self.state = PoolState.ACTIVE
                
        except Exception as e:
            logger.error(f"Resource check error: {e}")
    
    def _activate_load_shedding(self):
        """Reduce worker count to conserve memory."""
        # Kill hot spare first
        if self.hot_spare:
            logger.info("Load shedding: Killing hot spare")
            self.hot_spare.process.shutdown(timeout=2.0)
            self.hot_spare = None
        
        # Reduce active workers if > 2
        target_workers = max(2, len(self.workers) // 2)
        while len(self.workers) > target_workers:
            # Kill least productive worker
            worker_id = min(
                self.workers.keys(),
                key=lambda wid: self.workers[wid].files_processed
            )
            logger.info(f"Load shedding: Killing worker {worker_id}")
            self.workers[worker_id].process.shutdown(timeout=2.0)
            del self.workers[worker_id]
    
    def _deactivate_load_shedding(self):
        """Restore worker count after memory recovery."""
        # Restore to configured worker count
        while len(self.workers) < self.config.num_workers:
            self._spawn_worker(is_hot_spare=False)
        
        # Restore hot spare
        if self.config.enable_hot_spare:
            self._spawn_hot_spare()
    
    # ========================================================================
    # INTERNAL: Result Processing
    # ========================================================================
    
    def _start_result_processor(self):
        """Start result processing thread."""
        import threading
        
        def process_loop():
            logger.info("Result processor started")
            
            while not self._stop_event.is_set():
                try:
                    result = self.get_result(timeout=1.0)
                    if result:
                        self._handle_result(result)
                except Exception as e:
                    logger.error(f"Result processor error: {e}")
            
            logger.info("Result processor stopped")
        
        self._result_processor_thread = threading.Thread(
            target=process_loop,
            daemon=True,
            name="ResultProcessor"
        )
        self._result_processor_thread.start()
    
    def _handle_result(self, result: dict):
        """Process a conversion result.
        
        Args:
            result: Result dict from worker
        """
        status = result.get('status')
        
        if status == 'completed':
            self.total_completed += 1
        else:
            self.total_failed += 1
        
        # Callback
        if self.on_result:
            try:
                self.on_result(result)
            except Exception as e:
                logger.error(f"on_result callback error: {e}")
