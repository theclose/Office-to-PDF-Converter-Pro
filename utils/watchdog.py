"""
Watchdog & Health Monitoring System
=====================================
Monitors application and worker health for 24/7 stability.

Features:
- Worker health monitoring
- Automatic worker restart on failure
- Memory usage tracking
- Conversion success rate monitoring
"""

import os
import time
import logging
import threading
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

# Try to import psutil for system monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# =============================================================================
# HEALTH METRICS
# =============================================================================

@dataclass
class HealthMetrics:
    """Real-time health metrics."""
    timestamp: datetime = field(default_factory=datetime.now)
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    conversion_success_rate: float = 1.0
    active_workers: int = 0
    pending_jobs: int = 0
    total_conversions: int = 0
    failed_conversions: int = 0
    
    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy state."""
        # Unhealthy conditions:
        # - Memory > 2GB
        # - Success rate < 50%
        # - No active workers when jobs pending
        if self.memory_mb > 2048:
            return False
        if self.conversion_success_rate < 0.5 and self.total_conversions > 10:
            return False
        if self.active_workers == 0 and self.pending_jobs > 0:
            return False
        return True


# =============================================================================
# CONVERSION TRACKER
# =============================================================================

class ConversionTracker:
    """Tracks conversion history for success rate calculation."""
    
    def __init__(self, window_size: int = 100):
        """
        Args:
            window_size: Number of recent conversions to track
        """
        self.window_size = window_size
        self._history: deque = deque(maxlen=window_size)
        self._lock = threading.Lock()
    
    def record(self, success: bool, duration: float = 0.0):
        """Record a conversion result."""
        with self._lock:
            self._history.append({
                "success": success,
                "duration": duration,
                "timestamp": time.time()
            })
    
    def get_success_rate(self) -> float:
        """Get recent success rate."""
        with self._lock:
            if not self._history:
                return 1.0
            successful = sum(1 for r in self._history if r["success"])
            return successful / len(self._history)
    
    def get_avg_duration(self) -> float:
        """Get average conversion duration."""
        with self._lock:
            if not self._history:
                return 0.0
            durations = [r["duration"] for r in self._history if r["duration"] > 0]
            return sum(durations) / len(durations) if durations else 0.0
    
    def get_total(self) -> int:
        """Get total conversions tracked."""
        with self._lock:
            return len(self._history)
    
    def get_failed(self) -> int:
        """Get failed conversions count."""
        with self._lock:
            return sum(1 for r in self._history if not r["success"])


# =============================================================================
# WATCHDOG
# =============================================================================

class Watchdog:
    """
    Monitors application health and triggers recovery actions.
    
    Usage:
        watchdog = Watchdog()
        watchdog.start()
        
        # Register health check callbacks
        watchdog.on_unhealthy = lambda metrics: restart_workers()
        
        # Get current health
        metrics = watchdog.get_metrics()
        
        watchdog.stop()
    """
    
    CHECK_INTERVAL = 5.0  # seconds
    
    def __init__(
        self,
        parallel_converter=None,
        on_unhealthy: Optional[Callable[[HealthMetrics], None]] = None,
        on_worker_died: Optional[Callable[[int], None]] = None
    ):
        """
        Args:
            parallel_converter: ParallelConverter instance to monitor
            on_unhealthy: Callback when system becomes unhealthy
            on_worker_died: Callback when a worker process dies
        """
        self.parallel_converter = parallel_converter
        self.on_unhealthy = on_unhealthy
        self.on_worker_died = on_worker_died
        
        self.tracker = ConversionTracker()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_metrics: Optional[HealthMetrics] = None
        self._known_dead_workers: set = set()
    
    def start(self):
        """Start the watchdog monitoring thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("Watchdog started")
    
    def stop(self):
        """Stop the watchdog."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("Watchdog stopped")
    
    def record_conversion(self, success: bool, duration: float = 0.0):
        """Record a conversion for tracking."""
        self.tracker.record(success, duration)
    
    def get_metrics(self) -> HealthMetrics:
        """Get current health metrics."""
        metrics = HealthMetrics()
        metrics.timestamp = datetime.now()
        
        # System metrics
        if HAS_PSUTIL:
            try:
                process = psutil.Process()
                metrics.memory_mb = process.memory_info().rss / (1024 * 1024)
                metrics.cpu_percent = process.cpu_percent(interval=0.1)
            except Exception:
                pass
        
        # Conversion metrics
        metrics.conversion_success_rate = self.tracker.get_success_rate()
        metrics.total_conversions = self.tracker.get_total()
        metrics.failed_conversions = self.tracker.get_failed()
        
        # Worker metrics
        if self.parallel_converter is not None:
            try:
                status = self.parallel_converter.get_worker_status()
                metrics.active_workers = sum(1 for w in status if w["alive"])
                metrics.pending_jobs = self.parallel_converter.get_pending_count()
            except Exception:
                pass
        
        self._last_metrics = metrics
        return metrics
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                metrics = self.get_metrics()
                
                # Check health
                if not metrics.is_healthy():
                    logger.warning(f"System unhealthy: {metrics}")
                    if self.on_unhealthy:
                        try:
                            self.on_unhealthy(metrics)
                        except Exception as e:
                            logger.error(f"Unhealthy callback error: {e}")
                
                # Check for dead workers
                if self.parallel_converter is not None:
                    self._check_workers()
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            
            # Wait for next check
            self._stop_event.wait(self.CHECK_INTERVAL)
    
    def _check_workers(self):
        """Check for dead workers and trigger callbacks."""
        try:
            status = self.parallel_converter.get_worker_status()
            
            for worker in status:
                worker_id = worker["id"]
                is_alive = worker["alive"]
                
                if not is_alive and worker_id not in self._known_dead_workers:
                    # New dead worker
                    self._known_dead_workers.add(worker_id)
                    logger.warning(f"Worker {worker_id} died")
                    
                    if self.on_worker_died:
                        try:
                            self.on_worker_died(worker_id)
                        except Exception as e:
                            logger.error(f"Worker died callback error: {e}")
                
                elif is_alive and worker_id in self._known_dead_workers:
                    # Worker was restarted
                    self._known_dead_workers.remove(worker_id)
                    logger.info(f"Worker {worker_id} recovered")
                    
        except Exception as e:
            logger.error(f"Worker check error: {e}")


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_watchdog: Optional[Watchdog] = None


def get_watchdog() -> Watchdog:
    """Get or create global watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = Watchdog()
    return _watchdog


def start_watchdog(parallel_converter=None):
    """Start the global watchdog."""
    watchdog = get_watchdog()
    watchdog.parallel_converter = parallel_converter
    watchdog.start()
    return watchdog


def stop_watchdog():
    """Stop the global watchdog."""
    global _watchdog
    if _watchdog is not None:
        _watchdog.stop()
        _watchdog = None
