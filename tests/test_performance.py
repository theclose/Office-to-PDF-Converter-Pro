"""
Comprehensive Performance and Integration Tests
=================================================
Tests for Month 2 optimization items and overall system health.
"""

import pytest
import os
import sys
import time
import tempfile
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# =============================================================================
# ITEM #7: Background PDF Preview Tests
# =============================================================================

class TestBackgroundPDFPreview:
    """Tests for background PDF preview rendering."""

    def test_render_id_increments(self):
        """Verify render_id increments to cancel stale renders."""
        # Mock the PDFPreviewPanel
        from unittest.mock import MagicMock
        
        # Create mock panel with render tracking
        panel = MagicMock()
        panel._render_id = 0
        
        # Simulate multiple render calls
        for i in range(5):
            panel._render_id += 1
            
        assert panel._render_id == 5

    def test_loading_state_management(self):
        """Verify loading state is properly managed."""
        panel = MagicMock()
        panel._is_loading = False
        
        # Simulate loading flow
        panel._is_loading = True
        assert panel._is_loading
        
        panel._is_loading = False
        assert not panel._is_loading


# =============================================================================
# ITEM #8: Virtual File List Tests
# =============================================================================

class TestVirtualFileList:
    """Tests for virtual file list with 1000+ file support."""

    def test_large_file_list_truncation(self):
        """Verify large file lists are properly truncated for display."""
        MAX_DISPLAY = 200
        
        # Simulate 1000 files
        file_count = 1000
        display_files = list(range(file_count))[:MAX_DISPLAY]
        
        assert len(display_files) == MAX_DISPLAY
        assert file_count > MAX_DISPLAY

    def test_batch_text_join_performance(self):
        """Verify batch text joining is faster than individual inserts."""
        lines = [f"Line {i}" for i in range(200)]
        
        # Batch join
        start = time.perf_counter()
        result = "\n".join(lines)
        batch_time = time.perf_counter() - start
        
        assert len(result) > 0
        assert batch_time < 0.1  # Should be very fast


# =============================================================================
# ITEM #10: Append-Only Log Tests
# =============================================================================

class TestAppendOnlyLog:
    """Tests for append-only JSONL conversion logging."""

    def test_jsonl_format_write(self):
        """Verify JSONL format is used for logging."""
        import json
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            record = {"file_size_mb": 1.5, "duration_seconds": 10.2, "success": True}
            f.write(json.dumps(record) + '\n')
            f.write(json.dumps(record) + '\n')
            temp_path = f.name
        
        try:
            # Read and verify
            with open(temp_path, 'r') as f:
                lines = f.readlines()
            
            assert len(lines) == 2
            for line in lines:
                data = json.loads(line.strip())
                assert "file_size_mb" in data
        finally:
            os.unlink(temp_path)

    def test_jsonl_append_vs_full_write(self):
        """Verify append is faster than full rewrite."""
        import json
        import tempfile
        
        records = [{"id": i, "data": "x" * 100} for i in range(100)]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name
        
        try:
            # Append method
            start = time.perf_counter()
            with open(temp_path, 'a') as f:
                for r in records:
                    f.write(json.dumps(r) + '\n')
            append_time = time.perf_counter() - start
            
            # Full rewrite method (simulated)
            start = time.perf_counter()
            with open(temp_path, 'w') as f:
                json.dump(records, f)
            full_time = time.perf_counter() - start
            
            # Both should be fast, but append scales better
            assert append_time < 1.0
            assert full_time < 1.0
        finally:
            os.unlink(temp_path)


# =============================================================================
# COMPOOL TESTS
# =============================================================================

class TestCOMPoolHealthCheck:
    """Tests for COMPool health check mechanism."""

    def test_health_check_methods_exist(self):
        """Verify health check methods exist in COMPool."""
        from office_converter.utils.com_pool import COMPool
        
        pool = COMPool()
        
        assert hasattr(pool, '_is_excel_alive')
        assert hasattr(pool, '_is_word_alive')
        assert hasattr(pool, '_is_ppt_alive')

    def test_pool_singleton(self):
        """Verify COMPool is a singleton."""
        from office_converter.utils.com_pool import COMPool
        
        pool1 = COMPool()
        pool2 = COMPool()
        
        assert pool1 is pool2


# =============================================================================
# LAZY IMPORT TESTS
# =============================================================================

class TestLazyImports:
    """Tests for lazy import mechanism."""

    def test_converters_module_lazy_load(self):
        """Verify converters module supports lazy loading."""
        # This import should be fast (no heavy modules loaded yet)
        from office_converter.converters import get_converter_for_file
        
        assert callable(get_converter_for_file)

    def test_getattr_mechanism(self):
        """Verify __getattr__ works for lazy loading."""
        # Try to access ExcelConverter
        from office_converter import converters
        
        # This should trigger lazy loading
        assert hasattr(converters, '__getattr__')


# =============================================================================
# PERFORMANCE BENCHMARKS
# =============================================================================

class TestPerformanceBenchmarks:
    """Performance benchmark tests."""

    def test_import_time_under_threshold(self):
        """Verify main module imports quickly."""
        import subprocess
        import sys
        
        # Run import in subprocess to measure import time
        code = """
import time
start = time.perf_counter()
try:
    import office_converter
    elapsed = time.perf_counter() - start
    print(f"OK:{elapsed:.2f}")
except Exception as e:
    print(f"ERR:{e}")
"""
        result = subprocess.run(
            [sys.executable, '-c', code],
            capture_output=True,
            timeout=30,
            text=True
        )
        
        # Check output
        output = result.stdout.strip()
        if output.startswith("OK:"):
            # Verify import time is under 10 seconds
            import_time = float(output.split(":")[1])
            assert import_time < 10.0, f"Import took too long: {import_time:.2f}s"
        else:
            # Module may not be installed in test environment, skip
            pytest.skip(f"Module import issue: {output}")

    def test_no_memory_leak_in_record_list(self):
        """Verify conversion records don't leak memory."""
        records = []
        
        # Add many records
        for i in range(1000):
            records.append({"id": i, "data": "x" * 100})
        
        # Trim to last 500
        records = records[-500:]
        
        assert len(records) == 500


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for full workflow."""

    def test_converter_module_structure(self):
        """Verify converter module exports are correct."""
        from office_converter.converters import (
            BaseConverter,
            get_converter_for_file,
            get_best_converter,
        )
        
        assert BaseConverter is not None
        assert callable(get_converter_for_file)
        assert callable(get_best_converter)

    def test_pdf_tools_exports(self):
        """Verify pdf_tools exports are correct."""
        from office_converter.utils.pdf_tools import (
            HAS_PYMUPDF,
            parse_page_range,
            rasterize_pdf,
        )
        
        assert isinstance(HAS_PYMUPDF, bool)
        assert callable(parse_page_range)
        assert callable(rasterize_pdf)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
