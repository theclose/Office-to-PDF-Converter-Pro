"""
Phase 2: COM Lifecycle & Pool Tests
=====================================
Tests for COMPool singleton, health check, recycle, idle timeout,
thread-local COM, and concurrency.

Strategy: Inject mock win32com and pythoncom into sys.modules
BEFORE com_pool is imported, so no real COM calls happen.
"""

import sys
import pytest
import threading
from unittest.mock import MagicMock, patch, PropertyMock

# ===========================================================================
# MUST run before any com_pool import: inject mock modules into sys.modules
# ===========================================================================

# Create fake pythoncom module
_mock_pythoncom = MagicMock()
_mock_pythoncom.CoInitialize = MagicMock(return_value=None)
_mock_pythoncom.CoUninitialize = MagicMock()

# Create fake win32com hierarchy
_mock_dispatch = MagicMock()
_default_com_app = MagicMock()
_default_com_app.Version = "16.0"
_mock_dispatch.return_value = _default_com_app

_mock_win32com_client = MagicMock()
_mock_win32com_client.Dispatch = _mock_dispatch

_mock_win32com = MagicMock()
_mock_win32com.client = _mock_win32com_client

# Save originals and inject mocks
_orig_pythoncom = sys.modules.get('pythoncom')
_orig_win32com = sys.modules.get('win32com')
_orig_win32com_client = sys.modules.get('win32com.client')

sys.modules['pythoncom'] = _mock_pythoncom
sys.modules['win32com'] = _mock_win32com
sys.modules['win32com.client'] = _mock_win32com_client

# Force-reload com_pool with mocked modules
import importlib
if 'utils.com_pool' in sys.modules:
    importlib.reload(sys.modules['utils.com_pool'])
else:
    import utils.com_pool

from utils.com_pool import COMPool, get_pool, release_pool
import utils.com_pool as com_pool_module


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture(autouse=True)
def reset_pool():
    """Reset COMPool singleton state + mock call counts before each test."""
    # Cancel any timer
    if COMPool._idle_timer and hasattr(COMPool._idle_timer, 'cancel'):
        try:
            COMPool._idle_timer.cancel()
        except Exception:
            pass

    COMPool._instance = None
    COMPool._excel = None
    COMPool._word = None
    COMPool._ppt = None
    COMPool._excel_count = 0
    COMPool._word_count = 0
    COMPool._ppt_count = 0
    COMPool._idle_timer = None
    # B1: Reset health-check timestamps
    COMPool._excel_last_ok = 0.0
    COMPool._word_last_ok = 0.0
    COMPool._ppt_last_ok = 0.0

    # Reset call counts
    _mock_dispatch.reset_mock()
    _mock_pythoncom.reset_mock()
    _default_com_app.reset_mock()
    _default_com_app.Version = "16.0"
    _mock_dispatch.return_value = _default_com_app

    # Reset the global _pool
    com_pool_module._pool = None

    yield

    # Teardown
    if COMPool._idle_timer and hasattr(COMPool._idle_timer, 'cancel'):
        try:
            COMPool._idle_timer.cancel()
        except Exception:
            pass
    COMPool._instance = None
    COMPool._excel = None
    COMPool._word = None
    COMPool._ppt = None
    COMPool._idle_timer = None
    com_pool_module._pool = None


def teardown_module():
    """Restore original modules."""
    if _orig_pythoncom:
        sys.modules['pythoncom'] = _orig_pythoncom
    if _orig_win32com:
        sys.modules['win32com'] = _orig_win32com
    if _orig_win32com_client:
        sys.modules['win32com.client'] = _orig_win32com_client


# ===========================================================================
# 1. COMPool Singleton
# ===========================================================================

class TestCOMPoolSingleton:

    def test_same_instance(self):
        assert COMPool() is COMPool()

    def test_get_pool_singleton(self):
        assert get_pool() is get_pool()

    def test_release_pool(self):
        get_pool()
        assert com_pool_module._pool is not None
        release_pool()
        assert com_pool_module._pool is None


# ===========================================================================
# 2. get_excel — Create / Reuse / Health Check
# ===========================================================================

class TestGetExcel:

    def test_creates_com_on_first_call(self):
        pool = COMPool()
        excel = pool.get_excel()
        assert excel is _default_com_app
        _mock_dispatch.assert_called_with("Excel.Application")

    def test_reuses_existing(self):
        pool = COMPool()
        pool.get_excel()
        pool.get_excel()
        # Dispatch called only once
        _mock_dispatch.assert_called_once()

    def test_recreates_when_health_check_fails(self):
        pool = COMPool()
        pool.get_excel()

        # B1: Force health-check by expiring the timestamp
        pool._excel_last_ok = 0.0

        # Simulate dead COM object
        type(_default_com_app).Version = PropertyMock(
            side_effect=Exception("COM server dead")
        )
        new_app = MagicMock(Version="16.0")
        _mock_dispatch.return_value = new_app

        excel = pool.get_excel()
        assert _mock_dispatch.call_count >= 2

        # Restore property
        type(_default_com_app).Version = PropertyMock(return_value="16.0")


# ===========================================================================
# 3. Recycle at threshold
# ===========================================================================

class TestRecycle:

    def test_recycle_at_threshold(self):
        pool = COMPool()
        pool.RECYCLE_THRESHOLD = 3

        for _ in range(3):
            pool.get_excel()

        # Quit should be called when recycling
        _default_com_app.Quit.assert_called()

    def test_max_retry_returns_none(self):
        pool = COMPool()
        assert pool.get_excel(_retry_count=pool.MAX_RETRY) is None


# ===========================================================================
# 4. Idle Timeout
# ===========================================================================

class TestIdleTimeout:

    def test_on_idle_timeout_releases(self):
        pool = COMPool()
        pool.get_excel()
        pool._on_idle_timeout()
        _default_com_app.Quit.assert_called()
        assert pool._excel is None

    def test_idle_timer_created_on_get(self):
        pool = COMPool()
        pool.get_excel()
        # Timer should exist (mocked)
        assert pool._idle_timer is not None


# ===========================================================================
# 5. release_all
# ===========================================================================

class TestReleaseAll:

    def test_quits_all_three_apps(self):
        mx, mw, mp = MagicMock(), MagicMock(), MagicMock()
        pool = COMPool()
        pool._excel = mx
        pool._word = mw
        pool._ppt = mp

        pool.release_all()

        mx.Quit.assert_called_once()
        mw.Quit.assert_called_once()
        mp.Quit.assert_called_once()
        assert pool._excel is None
        assert pool._word is None
        assert pool._ppt is None

    def test_release_all_idempotent(self):
        pool = COMPool()
        pool.release_all()
        pool.release_all()  # Should not raise


# ===========================================================================
# 6. Thread-local COM (converters/base.py)
# ===========================================================================

class TestThreadLocalCOM:

    def test_ensure_com_init(self):
        # Use the mock pythoncom we injected
        from converters.base import ensure_com_initialized
        _mock_pythoncom.CoInitialize.reset_mock()
        ensure_com_initialized()
        _mock_pythoncom.CoInitialize.assert_called()

    def test_release_com(self):
        from converters.base import release_com
        _mock_pythoncom.CoUninitialize.reset_mock()
        release_com()
        _mock_pythoncom.CoUninitialize.assert_called()


# ===========================================================================
# 7. Stats
# ===========================================================================

class TestPoolStats:

    def test_stats_track_usage(self):
        pool = COMPool()
        pool.get_excel()
        pool.get_excel()
        stats = pool.get_stats()
        assert stats["excel_conversions"] == 2
        assert stats["word_conversions"] == 0
        assert stats["ppt_conversions"] == 0

    def test_get_word_tracked(self):
        pool = COMPool()
        _mock_dispatch.return_value = MagicMock(Version="16.0")
        pool.get_word()
        stats = pool.get_stats()
        assert stats["word_conversions"] == 1


# ===========================================================================
# 8. Concurrent access
# ===========================================================================

class TestConcurrency:

    def test_concurrent_get_excel_no_race(self):
        pool = COMPool()
        results, errors = [], []

        def go():
            try:
                results.append(pool.get_excel() is not None)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=go) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        assert not errors, f"Race condition errors: {errors}"
        assert all(results)


# ===========================================================================
# 9. P4 Regression: RECYCLE_THRESHOLD hardcoded (not read from config)
# ===========================================================================

class TestP4Regression:
    """P4: Verify config.json recycle_threshold is NOT read by COMPool."""

    def test_recycle_threshold_is_hardcoded(self):
        """COMPool.RECYCLE_THRESHOLD is a class constant = 50, not from config."""
        # It's a class variable, not read dynamically from Config singleton
        assert hasattr(COMPool, 'RECYCLE_THRESHOLD')
        assert COMPool.RECYCLE_THRESHOLD == 50
        # Verify it's truly a class var, not an instance property
        pool = COMPool()
        assert pool.RECYCLE_THRESHOLD == COMPool.RECYCLE_THRESHOLD

    def test_default_threshold_is_50(self):
        assert COMPool.RECYCLE_THRESHOLD == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
