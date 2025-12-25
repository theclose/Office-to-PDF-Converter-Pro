"""
Parallel Conversion System
============================
Multi-process conversion for 2-4x throughput improvement.

Each worker process has its own COM instance to avoid threading issues.
Uses multiprocessing Queue for job distribution and result collection.
"""

import os
import sys
import time
import logging
import multiprocessing as mp
from multiprocessing import Process, Queue, Event
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# =============================================================================
# DATA STRUCTURES
# =============================================================================

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ConversionJob:
    """A single conversion job."""
    job_id: str
    input_path: str
    output_path: str
    quality: str = "high"
    sheet_indices: Optional[List[int]] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConversionResult:
    """Result of a conversion job."""
    job_id: str
    success: bool
    duration: float
    error: Optional[str] = None
    output_path: Optional[str] = None


# =============================================================================
# WORKER PROCESS
# =============================================================================

def _worker_process(
    worker_id: int,
    job_queue: Queue,
    result_queue: Queue,
    stop_event: Event
):
    """
    Worker process that handles conversion jobs.
    Each worker has its own COM instance.
    """
    import pythoncom
    
    # Initialize COM for this process
    pythoncom.CoInitialize()
    
    logger.info(f"Worker {worker_id} started")
    
    try:
        while not stop_event.is_set():
            try:
                # Get job with timeout (allows checking stop_event)
                job_dict = job_queue.get(timeout=1.0)
                
                if job_dict is None:  # Poison pill
                    break
                    
                job = ConversionJob(**job_dict)
                start_time = time.perf_counter()
                
                try:
                    # Determine file type and get converter
                    ext = Path(job.input_path).suffix.lower()
                    
                    # Lazy import converters
                    from office_converter.converters import get_converter_for_file
                    
                    converter_class = get_converter_for_file(job.input_path)
                    if converter_class is None:
                        raise ValueError(f"No converter for {ext}")
                    
                    # Create converter instance
                    converter = converter_class()
                    
                    if not converter.initialize():
                        raise RuntimeError("Failed to initialize converter")
                    
                    try:
                        # Perform conversion
                        if converter.__class__.__name__ == "ExcelConverter" and job.sheet_indices:
                            success = converter.convert(
                                job.input_path,
                                job.output_path,
                                job.quality,
                                job.sheet_indices
                            )
                        else:
                            success = converter.convert(
                                job.input_path,
                                job.output_path,
                                job.quality
                            )
                    finally:
                        converter.cleanup()
                    
                    duration = time.perf_counter() - start_time
                    
                    result = ConversionResult(
                        job_id=job.job_id,
                        success=success,
                        duration=duration,
                        output_path=job.output_path if success else None
                    )
                    
                except Exception as e:
                    logger.error(f"Worker {worker_id} error: {e}")
                    duration = time.perf_counter() - start_time
                    result = ConversionResult(
                        job_id=job.job_id,
                        success=False,
                        duration=duration,
                        error=str(e)
                    )
                
                result_queue.put(asdict(result))
                
            except mp.queues.Empty:
                continue  # Timeout, check stop_event again
            except Exception as e:
                logger.error(f"Worker {worker_id} queue error: {e}")
                
    finally:
        # Cleanup COM
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        logger.info(f"Worker {worker_id} stopped")


# =============================================================================
# WORKER POOL MANAGER
# =============================================================================

class ParallelConverter:
    """
    Manages a pool of worker processes for parallel conversion.
    
    Usage:
        converter = ParallelConverter(num_workers=3)
        converter.start()
        
        # Submit jobs
        converter.submit(job1)
        converter.submit(job2)
        
        # Get results
        for result in converter.get_results():
            print(result)
        
        converter.stop()
    """
    
    DEFAULT_WORKERS = 2
    
    def __init__(
        self,
        num_workers: Optional[int] = None,
        on_result: Optional[Callable[[ConversionResult], None]] = None
    ):
        """
        Initialize parallel converter.
        
        Args:
            num_workers: Number of worker processes (default: CPU count / 2, max 4)
            on_result: Callback for each result
        """
        if num_workers is None:
            # Auto-detect: half of CPUs, min 1, max 4
            cpu_count = mp.cpu_count() or 2
            num_workers = max(1, min(4, cpu_count // 2))
        
        self.num_workers = num_workers
        self.on_result = on_result
        
        self.job_queue: Optional[Queue] = None
        self.result_queue: Optional[Queue] = None
        self.stop_event: Optional[Event] = None
        self.workers: List[Process] = []
        
        self._is_running = False
        self._job_counter = 0
        self._pending_jobs: Dict[str, ConversionJob] = {}
        
        logger.info(f"ParallelConverter initialized with {num_workers} workers")
    
    def start(self):
        """Start the worker pool."""
        if self._is_running:
            return
            
        self.job_queue = mp.Queue()
        self.result_queue = mp.Queue()
        self.stop_event = mp.Event()
        
        # Start workers
        for i in range(self.num_workers):
            worker = Process(
                target=_worker_process,
                args=(i, self.job_queue, self.result_queue, self.stop_event),
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
        
        self._is_running = True
        logger.info(f"Started {self.num_workers} workers")
    
    def stop(self, timeout: float = 5.0):
        """Stop all workers gracefully."""
        if not self._is_running:
            return
        
        # Signal stop
        self.stop_event.set()
        
        # Send poison pills
        for _ in self.workers:
            try:
                self.job_queue.put(None, timeout=1.0)
            except Exception:
                pass
        
        # Wait for workers
        for worker in self.workers:
            worker.join(timeout=timeout)
            if worker.is_alive():
                worker.terminate()
        
        self.workers.clear()
        self._is_running = False
        logger.info("All workers stopped")
    
    def submit(self, job: ConversionJob) -> str:
        """
        Submit a conversion job.
        
        Returns:
            Job ID
        """
        if not self._is_running:
            raise RuntimeError("ParallelConverter not started")
        
        if not job.job_id:
            self._job_counter += 1
            job.job_id = f"job_{self._job_counter}"
        
        self._pending_jobs[job.job_id] = job
        self.job_queue.put(job.to_dict())
        
        return job.job_id
    
    def get_results(self, block: bool = False, timeout: float = 0.1) -> List[ConversionResult]:
        """
        Get completed results.
        
        Args:
            block: Whether to block waiting for results
            timeout: Timeout for blocking wait
            
        Returns:
            List of completed results
        """
        results = []
        
        while True:
            try:
                result_dict = self.result_queue.get(block=block, timeout=timeout)
                result = ConversionResult(**result_dict)
                results.append(result)
                
                # Remove from pending
                if result.job_id in self._pending_jobs:
                    del self._pending_jobs[result.job_id]
                
                # Callback
                if self.on_result:
                    try:
                        self.on_result(result)
                    except Exception as e:
                        logger.error(f"Result callback error: {e}")
                
                if not block:
                    block = False  # Only block on first get
                    
            except mp.queues.Empty:
                break
        
        return results
    
    def get_pending_count(self) -> int:
        """Get number of pending jobs."""
        return len(self._pending_jobs)
    
    def is_running(self) -> bool:
        """Check if converter is running."""
        return self._is_running
    
    def get_worker_status(self) -> List[Dict[str, Any]]:
        """Get status of all workers."""
        status = []
        for i, worker in enumerate(self.workers):
            status.append({
                "id": i,
                "alive": worker.is_alive(),
                "pid": worker.pid
            })
        return status


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_global_converter: Optional[ParallelConverter] = None


def get_parallel_converter(num_workers: int = None) -> ParallelConverter:
    """Get or create global parallel converter."""
    global _global_converter
    
    if _global_converter is None or not _global_converter.is_running():
        _global_converter = ParallelConverter(num_workers)
        _global_converter.start()
    
    return _global_converter


def shutdown_parallel_converter():
    """Shutdown global parallel converter."""
    global _global_converter
    
    if _global_converter is not None:
        _global_converter.stop()
        _global_converter = None
