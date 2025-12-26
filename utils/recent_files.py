"""
Recent Files Database - SQLite-based storage for file history.
Extracted from main_window_pro.py for better modularity.
"""

import os
import sqlite3
import threading
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class RecentFilesDB:
    """SQLite database for recent files and history with connection pooling."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default location.
        """
        if db_path is None:
            # Default to package directory
            package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(package_dir, "converter_history.db")
            
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create persistent connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Enable WAL mode for better concurrent reads
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self):
        """Initialize database tables and indexes."""
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS recent_files (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        path TEXT UNIQUE,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        use_count INTEGER DEFAULT 1
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS conversion_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        input_path TEXT,
                        output_path TEXT,
                        status TEXT,
                        duration REAL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # P1 Performance: Add index for ORDER BY last_used DESC queries
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_recent_last_used 
                    ON recent_files(last_used DESC)
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Database init error: {e}")

    def add_recent(self, path: str):
        """Add or update recent file."""
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute("""
                    INSERT INTO recent_files (path, last_used, use_count)
                    VALUES (?, CURRENT_TIMESTAMP, 1)
                    ON CONFLICT(path) DO UPDATE SET
                        last_used = CURRENT_TIMESTAMP,
                        use_count = use_count + 1
                """, (path,))
                conn.commit()
        except Exception as e:
            logger.error(f"Add recent error: {e}")

    def get_recent(self, limit: int = 10) -> List[str]:
        """Get recent files ordered by last used."""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute("""
                    SELECT path FROM recent_files
                    WHERE path IS NOT NULL
                    ORDER BY last_used DESC
                    LIMIT ?
                """, (limit,))
                return [row[0] for row in cursor.fetchall() if os.path.exists(row[0])]
        except Exception as e:
            logger.error(f"Get recent error: {e}")
            return []

    def log_conversion(self, input_path: str, output_path: str,
                       status: str, duration: float):
        """Log conversion result."""
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute("""
                    INSERT INTO conversion_history 
                    (input_path, output_path, status, duration)
                    VALUES (?, ?, ?, ?)
                """, (input_path, output_path, status, duration))
                conn.commit()
        except Exception as e:
            logger.error(f"Log conversion error: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get conversion statistics."""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success,
                        AVG(duration) as avg_duration
                    FROM conversion_history
                """)
                row = cursor.fetchone()
                total, success, avg_duration = row
                return {
                    "total": total or 0,
                    "success": success or 0,
                    "failed": (total or 0) - (success or 0),
                    "success_rate": (success / total * 100) if total else 0,
                    "avg_duration": avg_duration or 0
                }
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return {"total": 0, "success": 0, "failed": 0, "success_rate": 0, "avg_duration": 0}

    def clear_history(self):
        """Clear all conversion history (keep recent files)."""
        try:
            with self._lock:
                conn = self._get_connection()
                conn.execute("DELETE FROM conversion_history")
                conn.commit()
        except Exception as e:
            logger.error(f"Clear history error: {e}")

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global instance
_db: Optional[RecentFilesDB] = None


def get_recent_files_db() -> RecentFilesDB:
    """Get global RecentFilesDB instance."""
    global _db
    if _db is None:
        _db = RecentFilesDB()
    return _db
