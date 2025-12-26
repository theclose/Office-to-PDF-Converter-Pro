"""
Worker Process - Isolated Conversion Executor

Each worker runs in a separate process to:
1. Isolate COM crashes (one worker dies, others continue)
2. Enable parallel processing across CPU cores
3. Implement circuit breaker pattern per worker
4. Support graceful shutdown and hot spare promotion

Architecture:
- Multiprocessing.Process subclass
- Dedicated COM apartment per worker (pythoncom.CoInitialize)
- Heartbeat mechanism for health monitoring
- Adaptive timeout execution
"""

import os
import sys
import time
import signal
import logging
import multiprocessing as mp
from dataclasses import dataclass
from typing import Optional, Callable
from pathlib import Path

# Add paths for imports in multiprocessing context
# Worker runs in separate process, needs explicit path setup
_grid_dir = Path(__file__).parent
_package_dir = _grid_dir.parent  # office_converter
_project_dir = _package_dir.parent  # Auto (contains office_converter)

# Add project dir first (for "from office_converter.xxx" imports)
if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))
# Add package dir (for relative "from grid.xxx" imports)
if str(_package_dir) not in sys.path:
    sys.path.insert(0, str(_package_dir))

from grid.models import ConversionFile, CircuitBreakerState


# Setup logging for worker process
logging.basicConfig(
    level=logging.INFO,
    format='[Worker-%(process)d] %(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for worker process."""
    worker_id: int
    base_timeout: float = 30.0  # Base timeout in seconds
    rate_mb_per_sec: float = 2.0  # Expected conversion throughput
    heartbeat_interval: float = 5.0  # Seconds between heartbeats
    max_consecutive_failures: int = 3  # Before worker restarts itself


class WorkerProcess(mp.Process):
    """Isolated worker process for file conversion.
    
    Each worker:
    - Initializes its own COM apartment
    - Receives files via IPC queue
    - Sends results via IPC queue
    - Emits heartbeats for health monitoring
    - Implements circuit breaker per file
    
    Lifecycle:
    1. __init__ → configure worker
    2. start() → spawn process
    3. run() → main loop (receive → convert → send result)
    4. shutdown() → graceful cleanup
    """
    
    def __init__(
        self,
        worker_id: int,
        task_queue: mp.Queue,
        result_queue: mp.Queue,
        heartbeat_queue: mp.Queue,
        config: Optional[WorkerConfig] = None
    ):
        """Initialize worker process.
        
        Args:
            worker_id: Unique identifier for this worker
            task_queue: Queue to receive ConversionFile objects
            result_queue: Queue to send conversion results
            heartbeat_queue: Queue to emit periodic heartbeats
            config: Worker configuration (uses defaults if None)
        """
        super().__init__(name=f"Worker-{worker_id}")
        
        self.worker_id = worker_id
        self.task_queue = task_queue
        self.result_queue = result_queue
        self.heartbeat_queue = heartbeat_queue
        self.config = config or WorkerConfig(worker_id=worker_id)
        
        # Internal state (set in child process)
        self._stop_event = mp.Event()
        self._last_heartbeat = 0.0
        self._files_processed = 0
        self._files_failed = 0
        self._circuit_breakers = {}  # file_hash -> CircuitBreakerState
        
    def run(self):
        """Main worker loop (runs in child process).
        
        This method executes in the spawned process, NOT the parent.
        """
        try:
            # Initialize COM for this process
            self._init_com()
            
            logger.info(f"Worker {self.worker_id} started (PID: {os.getpid()})")
            
            # Send initial heartbeat
            self._send_heartbeat()
            
            # Main processing loop
            while not self._stop_event.is_set():
                try:
                    # Check for new task (non-blocking with timeout)
                    task = self.task_queue.get(timeout=1.0)
                    
                    if task is None:
                        # Poison pill - shutdown signal
                        logger.info(f"Worker {self.worker_id} received shutdown signal")
                        break
                    
                    # Process the file
                    result = self._process_file(task)
                    
                    # Send result back
                    self.result_queue.put(result)
                    
                    # Update stats
                    if result.get('status') == 'completed':
                        self._files_processed += 1
                    else:
                        self._files_failed += 1
                    
                    # Periodic heartbeat
                    self._maybe_send_heartbeat()
                    
                except mp.queues.Empty:
                    # No task available, send heartbeat and continue
                    self._maybe_send_heartbeat()
                    continue
                    
                except Exception as e:
                    logger.error(f"Worker {self.worker_id} error in main loop: {e}")
                    # Continue processing despite error
                    
        except KeyboardInterrupt:
            logger.info(f"Worker {self.worker_id} interrupted")
            
        finally:
            # Cleanup
            self._cleanup_com()
            logger.info(
                f"Worker {self.worker_id} shutting down. "
                f"Processed: {self._files_processed}, Failed: {self._files_failed}"
            )
    
    def _init_com(self):
        """Initialize COM apartment for this process."""
        try:
            import pythoncom
            pythoncom.CoInitialize()
            logger.info(f"Worker {self.worker_id} initialized COM apartment")
        except Exception as e:
            logger.error(f"Worker {self.worker_id} COM init failed: {e}")
            raise
    
    def _cleanup_com(self):
        """Cleanup COM apartment."""
        try:
            import pythoncom
            pythoncom.CoUninitialize()
        except Exception as e:
            logger.debug(f"Worker {self.worker_id} COM cleanup error: {e}")
    
    def _process_file(self, file: ConversionFile) -> dict:
        """Process a single file with circuit breaker.
        
        Args:
            file: ConversionFile to process
            
        Returns:
            Dict with status, output_path, error, duration
        """
        start_time = time.time()
        
        # Check circuit breaker
        circuit_state = self._circuit_breakers.get(
            file.file_hash,
            CircuitBreakerState(file_hash=file.file_hash)
        )
        
        if not circuit_state.should_allow_attempt(time.time()):
            # Circuit is OPEN, reject immediately
            logger.warning(
                f"Worker {self.worker_id} - Circuit OPEN for {file.filename}, skipping"
            )
            return {
                'file': file,
                'status': 'quarantined',
                'error': f'Circuit breaker OPEN (failed {circuit_state.failure_count} times)',
                'duration': 0.0,
            }
        
        # Calculate adaptive timeout
        timeout = file.compute_timeout(
            base_timeout=self.config.base_timeout,
            rate_mb_per_sec=self.config.rate_mb_per_sec
        )
        
        logger.info(
            f"Worker {self.worker_id} processing {file.filename} "
            f"({file.file_size_bytes // 1024}KB, timeout={timeout:.1f}s)"
        )
        
        try:
            # Attempt conversion with timeout
            result = self._convert_with_timeout(file, timeout)
            
            if result['status'] == 'completed':
                # Success - reset circuit breaker
                circuit_state.record_success()
                logger.info(
                    f"Worker {self.worker_id} completed {file.filename} "
                    f"in {result['duration']:.2f}s"
                )
            else:
                # Failure - record in circuit breaker
                circuit_state.record_failure(
                    time.time(),
                    threshold=self.config.max_consecutive_failures
                )
                logger.error(
                    f"Worker {self.worker_id} failed {file.filename}: {result.get('error')}"
                )
            
            # Update circuit breaker state
            self._circuit_breakers[file.file_hash] = circuit_state
            
            # Add duration
            result['duration'] = time.time() - start_time
            
            return result
            
        except Exception as e:
            # Unexpected error
            logger.error(f"Worker {self.worker_id} exception: {e}")
            circuit_state.record_failure(
                time.time(),
                threshold=self.config.max_consecutive_failures
            )
            self._circuit_breakers[file.file_hash] = circuit_state
            
            return {
                'file': file,
                'status': 'failed',
                'error': str(e),
                'duration': time.time() - start_time,
            }
    
    def _convert_with_timeout(self, file: ConversionFile, timeout: float) -> dict:
        """Execute conversion with timeout enforcement.
        
        Args:
            file: ConversionFile to convert
            timeout: Maximum seconds to allow
            
        Returns:
            Dict with status, output_path, error
        """
        # Import converter with absolute path (required for multiprocessing)
        # The office_converter package must be importable from sys.path
        from office_converter.converters.base import get_converter_for_file
        
        # Get converter class
        converter_class = get_converter_for_file(file.path)
        if not converter_class:
            return {
                'file': file,
                'status': 'failed',
                'error': f'No converter found for {file.file_type}',
            }
        
        # Create converter instance
        converter = converter_class()
        
        try:
            # Initialize COM application
            if not converter.initialize():
                return {
                    'file': file,
                    'status': 'failed',
                    'error': 'Failed to initialize COM application',
                }
            
            # Determine output path (same directory as input)
            output_path = str(Path(file.path).with_suffix('.pdf'))
            
            # Execute conversion with timeout
            # Note: Python doesn't have built-in function timeout, so we use signal (Unix) or threading (Windows)
            success = self._execute_with_timeout(
                lambda: converter.convert(file.path, output_path, quality=0),
                timeout
            )
            
            if success:
                return {
                    'file': file,
                    'status': 'completed',
                    'output_path': output_path,
                }
            else:
                return {
                    'file': file,
                    'status': 'failed',
                    'error': f'Conversion timed out after {timeout}s',
                }
                
        finally:
            # Always cleanup converter
            try:
                converter.cleanup()
            except Exception:
                pass
    
    def _execute_with_timeout(self, func: Callable, timeout: float) -> bool:
        """Execute function with timeout.
        
        Args:
            func: Function to execute
            timeout: Maximum seconds
            
        Returns:
            True if completed, False if timed out
        """
        if sys.platform == 'win32':
            # Windows: Use threading (signal not reliable on Windows)
            import threading
            
            result = [None]
            exception = [None]
            
            def target():
                try:
                    result[0] = func()
                except Exception as e:
                    exception[0] = e
            
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout)
            
            if thread.is_alive():
                # Timeout occurred
                logger.warning("Conversion timeout - thread still alive")
                return False
            
            if exception[0]:
                raise exception[0]
            
            return result[0] is not False  # None or True = success
            
        else:
            # Unix: Use signal
            def timeout_handler(signum, frame):
                raise TimeoutError("Conversion timed out")
            
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))
            
            try:
                result = func()
                signal.alarm(0)  # Cancel alarm
                return result is not False
            except TimeoutError:
                return False
            finally:
                signal.signal(signal.SIGALRM, old_handler)
    
    def _send_heartbeat(self):
        """Send heartbeat to monitoring queue."""
        try:
            self.heartbeat_queue.put({
                'worker_id': self.worker_id,
                'pid': os.getpid(),
                'timestamp': time.time(),
                'files_processed': self._files_processed,
                'files_failed': self._files_failed,
                'active_circuits': len([
                    cb for cb in self._circuit_breakers.values()
                    if cb.state == 'OPEN'
                ]),
            })
            self._last_heartbeat = time.time()
        except Exception as e:
            logger.error(f"Worker {self.worker_id} heartbeat error: {e}")
    
    def _maybe_send_heartbeat(self):
        """Send heartbeat if interval elapsed."""
        if time.time() - self._last_heartbeat >= self.config.heartbeat_interval:
            self._send_heartbeat()
    
    def shutdown(self, timeout: float = 5.0):
        """Request graceful shutdown.
        
        Args:
            timeout: Seconds to wait for clean shutdown
        """
        logger.info(f"Worker {self.worker_id} shutdown requested")
        self._stop_event.set()
        
        # Send poison pill
        try:
            self.task_queue.put(None, timeout=1.0)
        except:
            pass
        
        # Wait for process to finish
        self.join(timeout)
        
        if self.is_alive():
            logger.warning(f"Worker {self.worker_id} did not shutdown cleanly, terminating")
            self.terminate()
            self.join(1.0)
