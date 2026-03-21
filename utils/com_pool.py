"""
COM Connection Pool - Manages and reuses COM application instances.
Implements Singleton pattern for each Office application.
"""

import logging
import time
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
    
    IMPORTANT: Callers MUST call pythoncom.CoInitialize() on their own thread
    before requesting COM instances from this pool. The pool's CoInitialize
    only covers the thread that first created the instance, NOT subsequent
    threads that retrieve it.
    """

    _instance = None
    _lock = threading.RLock()  # Must be RLock: __new__ holds lock + calls _reset_idle_timer which also acquires it

    # Idle timeout (5 minutes)
    IDLE_TIMEOUT = 300
    _idle_timer: Optional[threading.Timer] = None

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

    # B1: Skip health-check if last successful use was within this interval
    HEALTH_CHECK_INTERVAL = 30  # seconds
    _excel_last_ok: float = 0.0
    _word_last_ok: float = 0.0
    _ppt_last_ok: float = 0.0

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Start idle timer when pool is first created
                    cls._instance._reset_idle_timer()
        return cls._instance

    def _reset_idle_timer(self):
        """Reset the idle timeout timer."""
        with self._lock:
            if self._idle_timer:
                self._idle_timer.cancel()
            self._idle_timer = threading.Timer(self.IDLE_TIMEOUT, self._on_idle_timeout)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def _on_idle_timeout(self):
        """Called when pool has been idle for IDLE_TIMEOUT seconds."""
        logger.info("COM Pool idle timeout reached. Releasing all COM instances to free memory.")
        self.release_all()

    def _is_excel_alive(self) -> bool:
        """Check if Excel instance is still alive and responsive."""
        if self._excel is None:
            return False
        try:
            # Try to access a simple property - if COM server is dead, this fails
            _ = self._excel.Version
            return True
        except Exception:
            logger.warning("Excel COM instance is dead, will recreate")
            self._excel = None
            return False

    def _is_word_alive(self) -> bool:
        """Check if Word instance is still alive and responsive."""
        if self._word is None:
            return False
        try:
            _ = self._word.Version
            return True
        except Exception:
            logger.warning("Word COM instance is dead, will recreate")
            self._word = None
            return False

    def _is_ppt_alive(self) -> bool:
        """Check if PowerPoint instance is still alive and responsive."""
        if self._ppt is None:
            return False
        try:
            _ = self._ppt.Version
            return True
        except Exception:
            logger.warning("PowerPoint COM instance is dead, will recreate")
            self._ppt = None
            return False

    @staticmethod
    def _kill_zombie_office(process_name: str):
        """Kill zombie Office processes that block new COM creation.
        
        When Office crashes, the process may linger as a zombie.
        Dispatch() connects to the zombie instead of creating new.
        """
        import subprocess
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", process_name],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                logger.info(f"Killed zombie {process_name}")
                time.sleep(1)  # Wait for process to fully exit
            else:
                logger.debug(f"No {process_name} to kill: {result.stderr.strip()}")
        except Exception as e:
            logger.debug(f"Zombie kill failed for {process_name}: {e}")

    def get_excel(self, _retry_count: int = 0) -> Optional[Any]:
        """Get or create Excel COM instance."""
        if _retry_count >= self.MAX_RETRY:
            logger.error("Max retries exceeded for Excel COM creation")
            return None

        with self._lock:
            # B1: Only health-check if last successful use was >30s ago
            if self._excel is not None:
                if time.time() - self._excel_last_ok > self.HEALTH_CHECK_INTERVAL:
                    if not self._is_excel_alive():
                        self._excel = None
            
            if self._excel is None:
                try:
                    pythoncom.CoInitialize()
                    self._excel = win32com.client.Dispatch("Excel.Application")
                    # Post-creation alive check — Dispatch may connect to zombie
                    try:
                        _ = self._excel.Version
                    except Exception:
                        logger.warning("New Excel COM is dead (zombie process), killing and retrying")
                        self._excel = None
                        self._kill_zombie_office("EXCEL.EXE")
                        return self.get_excel(_retry_count + 1)
                    self._configure_excel(self._excel)
                    self._excel_count = 0
                    logger.info("Excel COM created (pooled)")
                except Exception as e:
                    logger.error(f"Failed to create Excel: {e}")
                    return None

            self._excel_count += 1
            self._excel_last_ok = time.time()
            self._reset_idle_timer()

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
            # B1: Only health-check if last successful use was >30s ago
            if self._word is not None:
                if time.time() - self._word_last_ok > self.HEALTH_CHECK_INTERVAL:
                    if not self._is_word_alive():
                        self._word = None
            
            if self._word is None:
                try:
                    pythoncom.CoInitialize()
                    self._word = win32com.client.Dispatch("Word.Application")
                    # Post-creation alive check — Dispatch may connect to zombie
                    try:
                        _ = self._word.Version
                    except Exception:
                        logger.warning("New Word COM is dead (zombie process), killing and retrying")
                        self._word = None
                        self._kill_zombie_office("WINWORD.EXE")
                        return self.get_word(_retry_count + 1)
                    self._configure_word(self._word)
                    self._word_count = 0
                    logger.info("Word COM created (pooled)")
                except Exception as e:
                    logger.error(f"Failed to create Word: {e}")
                    return None

            self._word_count += 1
            self._word_last_ok = time.time()
            self._reset_idle_timer()

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
            # B1: Only health-check if last successful use was >30s ago
            if self._ppt is not None:
                if time.time() - self._ppt_last_ok > self.HEALTH_CHECK_INTERVAL:
                    if not self._is_ppt_alive():
                        self._ppt = None
            
            if self._ppt is None:
                try:
                    pythoncom.CoInitialize()
                    self._ppt = win32com.client.Dispatch("PowerPoint.Application")
                    # Post-creation alive check — Dispatch may connect to zombie
                    try:
                        _ = self._ppt.Version
                    except Exception:
                        logger.warning("New PPT COM is dead (zombie process), killing and retrying")
                        self._ppt = None
                        self._kill_zombie_office("POWERPNT.EXE")
                        return self.get_ppt(_retry_count + 1)
                    self._configure_ppt(self._ppt)
                    self._ppt_count = 0
                    logger.info("PowerPoint COM created (pooled)")
                except Exception as e:
                    logger.error(f"Failed to create PowerPoint: {e}")
                    return None

            self._ppt_count += 1
            self._ppt_last_ok = time.time()
            self._reset_idle_timer()

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

    def invalidate_word(self):
        """Force-invalidate cached Word COM (called when converter detects dead proxy)."""
        with self._lock:
            self._word = None
            self._word_last_ok = 0.0
            logger.info("Word COM invalidated by converter")

    def invalidate_excel(self):
        """Force-invalidate cached Excel COM."""
        with self._lock:
            self._excel = None
            self._excel_last_ok = 0.0
            logger.info("Excel COM invalidated by converter")

    def invalidate_ppt(self):
        """Force-invalidate cached PowerPoint COM."""
        with self._lock:
            self._ppt = None
            self._ppt_last_ok = 0.0
            logger.info("PowerPoint COM invalidated by converter")

    def release_all(self):
        """Release all COM instances."""
        with self._lock:
            self._recycle_excel()
            self._recycle_word()
            self._recycle_ppt()
            if self._idle_timer:
                self._idle_timer.cancel()
                self._idle_timer = None
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
