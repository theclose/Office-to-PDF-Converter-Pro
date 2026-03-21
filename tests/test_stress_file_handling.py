"""
Stress tests: File handling, temp file cleanup, concurrency.
Catches bugs like Trap #18 (OCR temp file locked by subprocess).

These tests verify that file operations are safe under stress:
repeated operations, concurrent access, and proper temp cleanup.
"""

import os
import gc
import glob
import shutil
import tempfile
import threading
import time
import pytest
from tests.conftest_integration import create_test_pdf


class TestTempFileCleanup:
    """Verify no temp files leak after operations."""

    def test_temp_file_cleanup_after_compress(self):
        """Compression must not leave temp files behind."""
        from office_converter.core.pdf.compression import compress_pdf

        # Count temp files before
        tmp_dir = tempfile.gettempdir()
        before = set(glob.glob(os.path.join(tmp_dir, "tmp*.pdf")))

        pdf = create_test_pdf(pages=2, with_image=True)
        fd, out = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        try:
            success, _ = compress_pdf(pdf, out, quality="medium")
        finally:
            for f in [pdf, out]:
                if os.path.exists(f):
                    os.remove(f)

        # Wait briefly for any cleanup
        time.sleep(0.5)
        after = set(glob.glob(os.path.join(tmp_dir, "tmp*.pdf")))

        leaked = after - before
        assert len(leaked) == 0, f"Temp PDF files leaked: {leaked}"

    def test_compress_same_file_10x(self):
        """Compressing the same PDF 10 times in sequence must not
        accumulate temp files or corrupt the PDF."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf = create_test_pdf(pages=3, with_image=True)
        try:
            for i in range(10):
                fd, out = tempfile.mkstemp(suffix=".pdf")
                os.close(fd)
                try:
                    success, _ = compress_pdf(pdf, out, quality="medium")
                    assert isinstance(success, bool), f"Iteration {i+1} returned non-bool"
                    if success:
                        assert os.path.getsize(out) > 0, f"Empty output at iteration {i+1}"
                finally:
                    if os.path.exists(out):
                        os.remove(out)
        finally:
            if os.path.exists(pdf):
                os.remove(pdf)

    def test_same_path_compress_10x(self):
        """In-place compression 10 times must keep file valid.
        Regression test for Trap #16."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf = create_test_pdf(pages=3, with_image=True)
        try:
            for i in range(10):
                success, _ = compress_pdf(pdf, pdf, quality="high")
                assert success is True, f"In-place compress failed at iteration {i+1}"
                assert os.path.exists(pdf), f"File disappeared at iteration {i+1}"
                assert os.path.getsize(pdf) > 0, f"File empty at iteration {i+1}"
        finally:
            if os.path.exists(pdf):
                os.remove(pdf)


class TestConcurrency:
    """Verify concurrent file operations don't cause corruption."""

    def test_concurrent_compress_2_files(self):
        """Two parallel compressions must not interfere with each other."""
        from office_converter.core.pdf.compression import compress_pdf

        pdf1 = create_test_pdf(pages=2, with_image=True)
        pdf2 = create_test_pdf(pages=3, with_image=True)
        fd1, out1 = tempfile.mkstemp(suffix=".pdf")
        os.close(fd1)
        fd2, out2 = tempfile.mkstemp(suffix=".pdf")
        os.close(fd2)

        results = {}
        errors = []

        def compress_worker(name, inp, outp):
            try:
                success, reduction = compress_pdf(inp, outp, quality="medium")
                results[name] = (success, reduction)
            except Exception as e:
                errors.append(f"{name}: {e}")

        t1 = threading.Thread(target=compress_worker, args=("A", pdf1, out1))
        t2 = threading.Thread(target=compress_worker, args=("B", pdf2, out2))

        try:
            t1.start()
            t2.start()
            t1.join(timeout=30)
            t2.join(timeout=30)

            assert len(errors) == 0, f"Concurrent compression errors: {errors}"
            assert "A" in results and "B" in results
        finally:
            for f in [pdf1, pdf2, out1, out2]:
                if os.path.exists(f):
                    os.remove(f)

    def test_config_save_concurrent_writes(self):
        """Two threads writing config simultaneously must not corrupt file."""
        from office_converter.utils.config import Config

        config = Config()
        errors = []

        def writer(thread_id):
            try:
                for i in range(10):
                    config.set(f"test_key_{thread_id}", f"value_{i}", auto_save=False)
                    config.save()
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        t1 = threading.Thread(target=writer, args=(1,))
        t2 = threading.Thread(target=writer, args=(2,))

        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert len(errors) == 0, f"Concurrent config write errors: {errors}"

        # Cleanup test keys — remove from internal dict + save
        for key in ["test_key_1", "test_key_2"]:
            try:
                config._data.pop(key, None)
            except Exception:
                pass
        config.save()

    def test_progress_estimator_concurrent_log(self):
        """Multiple conversion logs in parallel must not corrupt history."""
        from office_converter.utils.progress_estimator import get_conversion_logger

        conv_logger = get_conversion_logger()
        errors = []

        pdf = create_test_pdf(pages=1)
        try:
            def log_worker(thread_id):
                try:
                    for i in range(10):
                        conv_logger.log_conversion(
                            file_path=pdf,
                            duration=1.0 + thread_id * 0.1,
                            success=True
                        )
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")

            threads = [threading.Thread(target=log_worker, args=(i,)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

            assert len(errors) == 0, f"Concurrent log errors: {errors}"
        finally:
            if os.path.exists(pdf):
                os.remove(pdf)
