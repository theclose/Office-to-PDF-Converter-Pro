"""
COM Connection Pool - Manages and reuses COM application instances.
Implements Singleton pattern for each Office application.
"""

import logging
import threading
import pythoncom
import win32com.client
from typing import Optional, Dict, Any
import gc

logger = logging.getLogger(__name__)


class COMPool:
    """
    Pool for managing COM application instances.
    Reuses instances instead of creating new ones for each conversion.
    Thread-safe with locking.
    """

    _instance = None
    _lock = threading.Lock()

    # Pool storage
    _excel: Optional[Any] = None
    _word: Optional[Any] = None
    _ppt: Optional[Any] = None

    # Usage counters for memory optimization
    _excel_count = 0
    _word_count = 0
    _ppt_count = 0

    # Auto-cleanup threshold (recycle after N conversions)
    RECYCLE_THRESHOLD = 50
    MAX_RETRY = 3

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_excel(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create Excel COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for Excel COM creation")
            return None

        with self._lock:
            if self._excel is None:
                try:
                    pythoncom.CoInitialize()
                    self._excel = win32com.client.Dispatch("Excel.Application")
                    self._configure_excel(self._excel)
                    self._excel_count = 0
                    logger.info("Excel COM created (pooled)")
                except Exception as e:
                    logger.error(f"Failed to create Excel: {e}")
                    return None

            self._excel_count += 1

            if self._excel_count >= self.RECYCLE_THRESHOLD:
                self._recycle_excel()
                return self.get_excel(_retry_count + 1)

            return self._excel

    def get_word(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create Word COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for Word COM creation")
            return None

        with self._lock:
            if self._word is None:
                try:
                    pythoncom.CoInitialize()
                    self._word = win32com.client.Dispatch("Word.Application")
                    self._configure_word(self._word)
                    self._word_count = 0
                    logger.info("Word COM created (pooled)")
                except Exception as e:
                    logger.error(f"Failed to create Word: {e}")
                    return None

            self._word_count += 1

            if self._word_count >= self.RECYCLE_THRESHOLD:
                self._recycle_word()
                return self.get_word(_retry_count + 1)

            return self._word

    def get_ppt(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create PowerPoint COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for PowerPoint COM creation")
            return None

        with self._lock:
            if self._ppt is None:
                try:
                    pythoncom.CoInitialize()
                    self._ppt = win32com.client.Dispatch("PowerPoint.Application")
                    self._configure_ppt(self._ppt)
                    self._ppt_count = 0
                    logger.info("PowerPoint COM created (pooled)")
                except Exception as e:
                    logger.error(f"Failed to create PowerPoint: {e}")
                    return None

            self._ppt_count += 1

            if self._ppt_count >= self.RECYCLE_THRESHOLD:
                self._recycle_ppt()
                return self.get_ppt(_retry_count + 1)

            return self._ppt

    def _configure_excel(self, app):
        """Configure Excel for silent operation."""
        try:
            app.Visible = False
            app.DisplayAlerts = False
            app.ScreenUpdating = False
            app.EnableEvents = False
            app.AskToUpdateLinks = False
            app.PrintCommunication = True
        except Exception as e:
            logger.debug(f"Excel pool configure: {e}")

    def _configure_word(self, app):
        """Configure Word for silent operation."""
        try:
            app.Visible = False
            app.DisplayAlerts = 0
            app.Options.CheckSpellingAsYouType = False
            app.Options.CheckGrammarAsYouType = False
            app.AutomationSecurity = 3
        except Exception as e:
            logger.debug(f"Word pool configure: {e}")

    def _configure_ppt(self, app):
        """Configure PowerPoint for silent operation."""
        try:
            app.DisplayAlerts = 0
        except Exception as e:
            logger.debug(f"PPT pool configure: {e}")

    def _recycle_excel(self):
        """Recycle Excel instance to free memory."""
        if self._excel:
            try:
                self._excel.Quit()
            except Exception as e:
                logger.debug(f"Excel recycle quit: {e}")
            self._excel = None
            gc.collect()
            logger.info("Excel COM recycled")

    def _recycle_word(self):
        """Recycle Word instance to free memory."""
        if self._word:
            try:
                self._word.Quit()
            except Exception as e:
                logger.debug(f"Word recycle quit: {e}")
            self._word = None
            gc.collect()
            logger.info("Word COM recycled")

    def _recycle_ppt(self):
        """Recycle PowerPoint instance to free memory."""
        if self._ppt:
            try:
                self._ppt.Quit()
            except Exception as e:
                logger.debug(f"PPT recycle quit: {e}")
            self._ppt = None
            gc.collect()
            logger.info("PowerPoint COM recycled")

    def release_all(self):
        """Release all COM instances. Call on app exit."""
        with self._lock:
            self._recycle_excel()
            self._recycle_word()
            self._recycle_ppt()
            logger.info("All COM instances released")

    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics."""
        return {
            "excel_conversions": self._excel_count,
            "word_conversions": self._word_count,
            "ppt_conversions": self._ppt_count
        }


# Global pool instance
_pool: Optional[COMPool] = None


def get_pool() -> COMPool:
    """Get global COM pool instance."""
    global _pool
    if _pool is None:
        _pool = COMPool()
    return _pool


def release_pool():
    """Release global COM pool."""
    global _pool
    if _pool:
        _pool.release_all()
        _pool = None
