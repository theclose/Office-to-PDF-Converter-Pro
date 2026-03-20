"""
Watchdog & Health Monitoring System
=====================================
Monitors application health during active conversions.
Designed to be an idle service that only runs when needed.

Features:
- Memory usage tracking 
- General CPU monitoring
- Conversion success rate tracking
"""

import os
import time
import logging
import threading
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

# Lazy-loaded psutil
_psutil = None

def _get_psutil():
    """Lazy import psutil on first use if it exists."""
    global _psutil
    if _psutil is None:
        try:
            import psutil
            _psutil = psutil
        except ImportError:
            _psutil = False
    return _psutil if _psutil is not False else None


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
    total_conversions: int = 0
    failed_conversions: int = 0
    
    def is_healthy(self) -> bool:
        """Check if metrics indicate healthy state."""
        # Unhealthy conditions:
        # - Memory > 2048 MB (2GB)
        # - Success rate < 50% after a reasonable sample size
        if self.memory_mb > 2048:
            return False
        if self.conversion_success_rate < 0.5 and self.total_conversions > 10:
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
    Monitors application health during active conversions.
    Only active while start() is called and stopped when jobs finish.
    """
    
    CHECK_INTERVAL = 5.0  # seconds
    
    def __init__(self, on_unhealthy: Optional[Callable[[HealthMetrics], None]] = None):
        """
        Args:
            on_unhealthy: Callback when system becomes unhealthy
        """
        self.on_unhealthy = on_unhealthy
        self.tracker = ConversionTracker()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_metrics: Optional[HealthMetrics] = None
        self._lock = threading.Lock()
    
    def start(self):
        """Start the watchdog monitoring thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
            logger.info("Watchdog started for active conversions")
    
    def stop(self):
        """Stop the watchdog."""
        self._stop_event.set()
        with self._lock:
            if self._thread is not None:
                self._thread.join(timeout=2.0)
                self._thread = None
            logger.info("Watchdog stopped (system idle)")
    
    def record_conversion(self, success: bool, duration: float = 0.0):
        """Record a conversion for tracking."""
        self.tracker.record(success, duration)
    
    def get_metrics(self) -> HealthMetrics:
        """Get current health metrics."""
        metrics = HealthMetrics()
        metrics.timestamp = datetime.now()
        
        # System metrics
        psutil = _get_psutil()
        if psutil:
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
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
            
            # Wait for next check
            self._stop_event.wait(self.CHECK_INTERVAL)

# Global instances for tracking if needed
_watchdog: Optional[Watchdog] = None

def get_watchdog() -> Watchdog:
    """Get or create global watchdog instance."""
    global _watchdog
    if _watchdog is None:
        _watchdog = Watchdog()
    return _watchdog

def start_watchdog():
    """Start the global watchdog."""
    watchdog = get_watchdog()
    watchdog.start()
    return watchdog

def stop_watchdog():
    """Stop the global watchdog."""
    global _watchdog
    if _watchdog is not None:
        _watchdog.stop()

def record_watchdog_conversion(success: bool, duration: float = 0.0):
    """Convenience method to record against global watchdog if it exists."""
    if _watchdog is not None:
        _watchdog.record_conversion(success, duration)
