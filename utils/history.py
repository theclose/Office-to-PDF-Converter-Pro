"""
Conversion History - Track and display conversion history.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversionRecord:
    """Single conversion record."""
    timestamp: str
    input_file: str
    output_file: str
    file_type: str  # excel, word, ppt
    success: bool
    duration: float
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversionRecord':
        return cls(**data)


class ConversionHistory:
    """Manages conversion history with file persistence."""

    MAX_RECORDS = 500  # Keep last 500 conversions

    def __init__(self, history_file: Optional[str] = None):
        if history_file is None:
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            history_file = os.path.join(package_dir, "conversion_history.json")

        self.history_file = history_file
        self.records: List[ConversionRecord] = []
        self._load()

    def _load(self):
        """Load history from file."""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.records = [ConversionRecord.from_dict(r) for r in data]
                logger.info(f"Loaded {len(self.records)} history records")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            self.records = []

    def _save(self):
        """Save history to file."""
        try:
            # Keep only last MAX_RECORDS
            if len(self.records) > self.MAX_RECORDS:
                self.records = self.records[-self.MAX_RECORDS:]

            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.records], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add(self, input_file: str, output_file: str, file_type: str,
            success: bool, duration: float, error: Optional[str] = None):
        """Add a conversion record."""
        record = ConversionRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            input_file=input_file,
            output_file=output_file,
            file_type=file_type,
            success=success,
            duration=round(duration, 2),
            error=error[:100] if error else None
        )
        self.records.append(record)
        self._save()

    def get_recent(self, count: int = 50) -> List[ConversionRecord]:
        """Get most recent records."""
        return list(reversed(self.records[-count:]))

    def get_stats(self) -> Dict:
        """Get conversion statistics."""
        total = len(self.records)
        success = sum(1 for r in self.records if r.success)
        failed = total - success

        by_type = {}
        for r in self.records:
            by_type[r.file_type] = by_type.get(r.file_type, 0) + 1

        avg_duration = 0
        if self.records:
            avg_duration = sum(r.duration for r in self.records) / total

        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": f"{(success/total*100):.1f}%" if total > 0 else "N/A",
            "by_type": by_type,
            "avg_duration": round(avg_duration, 2)
        }

    def clear(self):
        """Clear all history."""
        self.records = []
        self._save()

    def search(self, query: str) -> List[ConversionRecord]:
        """Search records by filename."""
        query = query.lower()
        return [r for r in self.records if query in r.input_file.lower() or query in r.output_file.lower()]


# Global instance
_history: Optional[ConversionHistory] = None


def get_history() -> ConversionHistory:
    """Get global history instance."""
    global _history
    if _history is None:
        _history = ConversionHistory()
    return _history
