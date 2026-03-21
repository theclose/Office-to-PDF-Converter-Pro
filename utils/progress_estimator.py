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
import json
import logging
import threading
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)

# SystemProfiler removed for performance optimization.
# System hardware profiling via psutil is no longer used to simplify the app.


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
    Stores data in JSON format for easy analysis. Thread-safe.
    """

    def __init__(self, log_dir: Optional[str] = None):
        """Initialize logger with storage directory."""
        if log_dir is None:
            # Default to user's app data directory
            log_dir = os.path.join(os.path.expanduser("~"), ".office_converter")

        self._lock = threading.Lock()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.log_dir / "conversion_history.json"
        self.system_file = self.log_dir / "system_profile.json"

        self.records: List[ConversionRecord] = []
        self._load_history()

        logger.info(f"ConversionLogger: {len(self.records)} historical records loaded")

    def _load_history(self):
        """Load historical records from file (supports both JSON and JSONL)."""
        try:
            # Try JSONL format first (new format)
            jsonl_file = self.log_dir / "conversion_history.jsonl"
            if jsonl_file.exists():
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                record = ConversionRecord.from_dict(json.loads(line))
                                self.records.append(record)
                            except Exception:
                                pass  # Skip malformed lines
                self.log_file = jsonl_file  # Use JSONL going forward
                return
            
            # Fall back to old JSON format
            if self.log_file.exists():
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.records = [ConversionRecord.from_dict(r) for r in data.get('records', [])]
                # Migrate to JSONL
                self._migrate_to_jsonl()
        except Exception as e:
            logger.warning(f"Error loading history: {e}")
            self.records = []

    def _migrate_to_jsonl(self):
        """Migrate old JSON format to append-only JSONL."""
        try:
            jsonl_file = self.log_dir / "conversion_history.jsonl"
            with open(jsonl_file, 'w', encoding='utf-8') as f:
                for record in self.records:
                    f.write(json.dumps(record.to_dict()) + '\n')
            self.log_file = jsonl_file
            logger.info(f"Migrated {len(self.records)} records to JSONL format")
        except Exception as e:
            logger.warning(f"Error migrating to JSONL: {e}")

    def _save_history(self):
        """Append-only save - only called for compaction."""
        # Note: Regular logging uses _append_record()
        # This is kept for compaction (trimming old records)
        try:
            jsonl_file = self.log_dir / "conversion_history.jsonl"
            # Keep only last 500 records
            records_to_save = self.records[-500:]
            with open(jsonl_file, 'w', encoding='utf-8') as f:
                for record in records_to_save:
                    f.write(json.dumps(record.to_dict()) + '\n')
            self.records = records_to_save
            logger.debug(f"Compacted history to {len(records_to_save)} records")
        except Exception as e:
            logger.warning(f"Error saving history: {e}")

    def _append_record(self, record: ConversionRecord):
        """Fast append-only write for new records."""
        try:
            jsonl_file = self.log_dir / "conversion_history.jsonl"
            with open(jsonl_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record.to_dict()) + '\n')
        except Exception as e:
            logger.warning(f"Error appending record: {e}")

    def log_conversion(self, file_path: str, duration: float, success: bool = True, **kwargs):
        """
        Log a conversion result (minimal data only).
        Uses append-only logging for performance.
        
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
            
            # Fast append instead of full rewrite
            self._append_record(record)
            
            # Periodic compaction (every 100 records over limit)
            if len(self.records) > 600:
                self._save_history()

            logger.debug(f"Logged: {file_size:.2f}MB = {duration:.1f}s")

        except Exception as e:
            logger.warning(f"Error logging conversion: {e}")

    # B4: get_records_by_type() removed — referenced nonexistent r.file_type field

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

    def __init__(self, conv_logger: ConversionLogger):
        """Initialize with logger. Pre-compute running totals for O(1) updates."""
        self.logger = conv_logger
        # T3: Running totals — avoids O(N) re-scan after every conversion
        records = [r for r in self.logger.records if r.success]
        self._total_time = sum(r.duration_seconds for r in records)
        self._total_size = sum(r.file_size_mb for r in records)
        self._record_count = len(records)
        self.avg_time_per_mb = self._compute_avg()

        logger.info(f"AdaptiveEstimator: avg_time_per_mb = {self.avg_time_per_mb:.2f}s/MB "
                   f"(from {self._record_count} records)")

    def _compute_avg(self) -> float:
        """Compute average time per MB from running totals. O(1)."""
        if self._total_size < 0.1:
            return self.DEFAULT_TIME_PER_MB
        avg = self._total_time / self._total_size
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
            success=success
        )

        # T3: O(1) incremental update instead of O(N) re-scan
        if success:
            try:
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                self._total_time += actual_duration
                self._total_size += file_size_mb
                self._record_count += 1
                self.avg_time_per_mb = self._compute_avg()
            except Exception:
                pass

        logger.debug(f"Updated avg_time_per_mb = {self.avg_time_per_mb:.2f}s/MB")


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

_logger: Optional[ConversionLogger] = None
_estimator: Optional[AdaptiveEstimator] = None


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
        _estimator = AdaptiveEstimator(get_conversion_logger())
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
