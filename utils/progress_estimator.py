"""
Adaptive Progress Estimation System
====================================
Intelligent progress estimation using machine learning from historical data.

Components:
- SystemProfiler: Detects and records system specifications
- ConversionLogger: Logs conversion history for learning
- AdaptiveEstimator: Predicts conversion time using historical data
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import psutil for system info
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not installed - using limited system detection")


# ============================================================================
# SYSTEM PROFILER
# ============================================================================

@dataclass
class SystemProfile:
    """System hardware profile."""
    cpu_name: str = "Unknown"
    cpu_cores: int = 4
    cpu_threads: int = 4
    ram_total_gb: float = 8.0
    ram_available_gb: float = 4.0
    disk_type: str = "Unknown"  # SSD or HDD
    performance_score: float = 1.0  # Normalized score (1.0 = baseline)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SystemProfile':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SystemProfiler:
    """
    Detects and records system hardware specifications.
    Used to normalize conversion time predictions across different machines.
    """
    
    # Baseline system (used for normalization)
    BASELINE_CORES = 4
    BASELINE_RAM_GB = 8.0
    
    def __init__(self):
        self.profile = self._detect_system()
        logger.info(f"SystemProfiler initialized: {self.profile.cpu_name}, "
                   f"{self.profile.cpu_cores}C/{self.profile.cpu_threads}T, "
                   f"{self.profile.ram_total_gb:.1f}GB RAM, "
                   f"Score: {self.profile.performance_score:.2f}")
    
    def _detect_system(self) -> SystemProfile:
        """Detect current system specifications."""
        profile = SystemProfile()
        
        if HAS_PSUTIL:
            try:
                # CPU info
                profile.cpu_cores = psutil.cpu_count(logical=False) or 4
                profile.cpu_threads = psutil.cpu_count(logical=True) or 4
                
                # Try to get CPU name
                try:
                    import platform
                    profile.cpu_name = platform.processor() or "Unknown CPU"
                except Exception:
                    pass
                
                # RAM info
                mem = psutil.virtual_memory()
                profile.ram_total_gb = mem.total / (1024 ** 3)
                profile.ram_available_gb = mem.available / (1024 ** 3)
                
                # Disk type detection (check system drive)
                try:
                    disk_info = psutil.disk_partitions()
                    if disk_info:
                        # Simple heuristic: SSDs typically have faster read speeds
                        profile.disk_type = "SSD"  # Assume SSD for modern systems
                except Exception:
                    pass
                    
            except Exception as e:
                logger.warning(f"Error detecting system: {e}")
        
        # Calculate performance score
        profile.performance_score = self._calculate_performance_score(profile)
        
        return profile
    
    def _calculate_performance_score(self, profile: SystemProfile) -> float:
        """
        Calculate normalized performance score.
        Score < 1.0 = faster than baseline
        Score > 1.0 = slower than baseline
        """
        # CPU factor (more cores = faster)
        cpu_factor = min(2.0, max(0.3, self.BASELINE_CORES / profile.cpu_cores))
        
        # RAM factor (more RAM = faster)
        ram_factor = min(2.0, max(0.3, self.BASELINE_RAM_GB / profile.ram_total_gb))
        
        # Combined score (CPU weighted more heavily)
        score = (cpu_factor * 0.6 + ram_factor * 0.4)
        
        return round(score, 3)
    
    def get_current_load(self) -> Dict[str, float]:
        """Get current CPU and RAM usage."""
        if HAS_PSUTIL:
            try:
                return {
                    'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'ram_percent': psutil.virtual_memory().percent
                }
            except Exception:
                pass
        return {'cpu_percent': 50.0, 'ram_percent': 50.0}


# ============================================================================
# CONVERSION LOGGER
# ============================================================================

@dataclass
class ConversionRecord:
    """Minimal conversion record - only what's needed for estimation."""
    file_size_mb: float      # File size in MB
    duration_seconds: float  # Actual conversion time
    success: bool = True     # Whether conversion succeeded
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ConversionRecord':
        # Handle both old format (with extra fields) and new minimal format
        return cls(
            file_size_mb=data.get('file_size_mb', 0),
            duration_seconds=data.get('duration_seconds', 0),
            success=data.get('success', True)
        )


class ConversionLogger:
    """
    Logs conversion history for machine learning.
    Stores data in JSON format for easy analysis.
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """Initialize logger with storage directory."""
        if log_dir is None:
            # Default to user's app data directory
            log_dir = os.path.join(os.path.expanduser("~"), ".office_converter")
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.log_dir / "conversion_history.json"
        self.system_file = self.log_dir / "system_profile.json"
        
        self.records: List[ConversionRecord] = []
        self._load_history()
        
        logger.info(f"ConversionLogger: {len(self.records)} historical records loaded")
    
    def _load_history(self):
        """Load historical records from file."""
        try:
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = [ConversionRecord.from_dict(r) for r in data.get('records', [])]
        except Exception as e:
            logger.warning(f"Error loading history: {e}")
            self.records = []
    
    def _save_history(self):
        """Save records to file."""
        try:
            data = {
                'version': '1.0',
                'last_updated': datetime.now().isoformat(),
                'record_count': len(self.records),
                'records': [r.to_dict() for r in self.records[-500:]]  # Keep last 500
            }
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Error saving history: {e}")
    
    def log_conversion(self, file_path: str, duration: float, success: bool = True, **kwargs):
        """
        Log a conversion result (minimal data only).
        
        Args:
            file_path: Path to converted file (used to get size)
            duration: Conversion time in seconds
            success: Whether conversion succeeded
        """
        try:
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
            
            record = ConversionRecord(
                file_size_mb=round(file_size, 3),
                duration_seconds=round(duration, 2),
                success=success
            )
            
            self.records.append(record)
            self._save_history()
            
            logger.debug(f"Logged: {file_size:.2f}MB = {duration:.1f}s")
            
        except Exception as e:
            logger.warning(f"Error logging conversion: {e}")
    
    def get_records_by_type(self, file_type: str) -> List[ConversionRecord]:
        """Get records filtered by file type."""
        return [r for r in self.records if r.file_type == file_type and r.success]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self.records:
            return {'count': 0}
        
        successful = [r for r in self.records if r.success]
        return {
            'count': len(self.records),
            'successful': len(successful),
            'avg_duration': sum(r.duration_seconds for r in successful) / len(successful) if successful else 0,
            'total_mb': sum(r.file_size_mb for r in successful),
        }


# ============================================================================

class AdaptiveEstimator:
    """
    Simple data-driven time estimator.
    
    Formula: estimated_time = file_size_mb × avg_time_per_mb
    Where: avg_time_per_mb = total_time / total_size (from all logs)
    
    The more logs, the more accurate the prediction.
    """
    
    # Default values when no log data available
    DEFAULT_TIME_PER_MB = 10.0  # 10 seconds per MB as starting point
    MIN_TIME = 3.0  # Minimum 3 seconds for any file (startup overhead)
    
    def __init__(self, conv_logger: ConversionLogger, profiler: SystemProfiler):
        """Initialize with logger."""
        self.logger = conv_logger
        self.profiler = profiler
        self.avg_time_per_mb = self._calculate_avg_time_per_mb()
        
        logger.info(f"AdaptiveEstimator: avg_time_per_mb = {self.avg_time_per_mb:.2f}s/MB "
                   f"(from {len(self.logger.records)} records)")
    
    def _calculate_avg_time_per_mb(self) -> float:
        """
        Calculate average time per MB from historical data.
        
        Returns:
            Average seconds per MB, or default if no data
        """
        records = [r for r in self.logger.records if r.success]
        
        if not records:
            return self.DEFAULT_TIME_PER_MB
        
        total_time = sum(r.duration_seconds for r in records)
        total_size = sum(r.file_size_mb for r in records)
        
        if total_size < 0.1:  # Avoid division by zero
            return self.DEFAULT_TIME_PER_MB
        
        avg = total_time / total_size
        
        # Sanity check: at least 1s/MB, at most 60s/MB
        return max(1.0, min(60.0, avg))
    
    def estimate(self, file_path: str, unit_count: int = 1) -> float:
        """
        Estimate conversion time for a file.
        
        Formula: max(MIN_TIME, file_size_mb × avg_time_per_mb)
        
        Args:
            file_path: Path to file
            unit_count: Unused, kept for compatibility
            
        Returns:
            Estimated time in seconds
        """
        try:
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            # Simple formula: size × avg_time_per_mb
            estimate = file_size_mb * self.avg_time_per_mb
            
            # Minimum time for startup overhead
            estimate = max(self.MIN_TIME, estimate)
            
            logger.debug(f"Estimate: {os.path.basename(file_path)} "
                        f"({file_size_mb:.2f}MB) = {estimate:.1f}s")
            
            return estimate
            
        except Exception as e:
            logger.warning(f"Error estimating: {e}")
            return 10.0  # Fallback
    
    def update_after_conversion(self, file_path: str, actual_duration: float,
                                 unit_count: int = 1, success: bool = True):
        """
        Log conversion and update average.
        
        Args:
            file_path: Path to converted file
            actual_duration: Actual conversion time
            unit_count: Unused
            success: Whether conversion succeeded
        """
        # Log the conversion
        self.logger.log_conversion(
            file_path=file_path,
            duration=actual_duration,
            success=success,
            system_score=self.profiler.profile.performance_score
        )
        
        # Recalculate average with new data
        self.avg_time_per_mb = self._calculate_avg_time_per_mb()
        
        logger.debug(f"Updated avg_time_per_mb = {self.avg_time_per_mb:.2f}s/MB")


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

_profiler: Optional[SystemProfiler] = None
_logger: Optional[ConversionLogger] = None
_estimator: Optional[AdaptiveEstimator] = None


def get_system_profiler() -> SystemProfiler:
    """Get global system profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = SystemProfiler()
    return _profiler


def get_conversion_logger() -> ConversionLogger:
    """Get global conversion logger instance."""
    global _logger
    if _logger is None:
        _logger = ConversionLogger()
    return _logger


def get_adaptive_estimator() -> AdaptiveEstimator:
    """Get global adaptive estimator instance."""
    global _estimator
    if _estimator is None:
        _estimator = AdaptiveEstimator(get_conversion_logger(), get_system_profiler())
    return _estimator


def estimate_conversion_time(file_path: str, unit_count: int = 1) -> float:
    """
    Convenience function to estimate conversion time.
    
    Args:
        file_path: Path to file
        unit_count: Number of sheets/pages/slides
        
    Returns:
        Estimated time in seconds
    """
    return get_adaptive_estimator().estimate(file_path, unit_count)


def log_conversion_result(file_path: str, duration: float, 
                          unit_count: int = 1, success: bool = True):
    """
    Log a conversion result for learning.
    
    Args:
        file_path: Path to converted file
        duration: Actual conversion time
        unit_count: Number of sheets/pages/slides
        success: Whether conversion succeeded
    """
    get_adaptive_estimator().update_after_conversion(file_path, duration, unit_count, success)
