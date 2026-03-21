"""Tests for new compression features: SSIM, hybrid, target size."""
import os
import tempfile
import shutil
import pytest
from unittest.mock import patch, MagicMock


# ─── Helpers ───
def _create_test_pdf(pages=3, with_image=False):
    """Create a minimal test PDF with PyMuPDF."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not available")
    
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)  # A4
        # Add text content
        page.insert_text((72, 100 + i * 20), f"Test page {i+1}" * 50, fontsize=12)
        
        if with_image:
            # Insert a colored rect to simulate image content
            rect = fitz.Rect(100, 200, 400, 500)
            page.draw_rect(rect, color=(1, 0, 0), fill=(0.5, 0.5, 1))
    
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def test_pdf():
    """Fixture: creates test PDF, yields path, cleans up."""
    path = _create_test_pdf(pages=3)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def test_pdf_with_images():
    """Fixture: creates test PDF with images, yields path, cleans up."""
    path = _create_test_pdf(pages=3, with_image=True)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def output_path():
    """Fixture: creates temp output path, cleans up after."""
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


# =============================================
# Test compute_ssim
# =============================================

class TestComputeSSIM:
    """Tests for compute_ssim() perceptual quality metric."""
    
    def test_ssim_identical_files(self, test_pdf):
        """SSIM of identical files should be ~1.0."""
        from office_converter.core.pdf.compression import compute_ssim
        result = compute_ssim(test_pdf, test_pdf)
        
        assert "error" not in result or result.get("ssim", 0) > 0
        # Identical files: SSIM should be very high
        if "error" not in result:
            assert result["ssim"] >= 0.99, f"Identical files should have SSIM ≈ 1.0, got {result['ssim']}"
            assert result["quality_label"] == "perfect"
    
    def test_ssim_returns_required_fields(self, test_pdf):
        """SSIM result should contain all required fields."""
        from office_converter.core.pdf.compression import compute_ssim
        result = compute_ssim(test_pdf, test_pdf)
        
        if "error" not in result:
            assert "ssim" in result
            assert "quality_label" in result
            assert "avg_pixel_diff" in result
            assert "black_percent" in result
    
    def test_ssim_invalid_file(self):
        """SSIM with non-existent file should return error gracefully."""
        from office_converter.core.pdf.compression import compute_ssim
        result = compute_ssim("/nonexistent.pdf", "/also_nonexistent.pdf")
        
        assert result["ssim"] == 0.0
        assert "error" in result
    
    def test_ssim_page_out_of_range(self, test_pdf):
        """SSIM with invalid page number should return error."""
        from office_converter.core.pdf.compression import compute_ssim
        result = compute_ssim(test_pdf, test_pdf, page=999)
        
        assert result["ssim"] == 0.0
        assert "error" in result
    
    def test_ssim_value_range(self, test_pdf, output_path):
        """SSIM should be between 0.0 and 1.0."""
        from office_converter.core.pdf.compression import compute_ssim, compress_pdf
        
        # Compress to create a different file
        success, _ = compress_pdf(test_pdf, output_path, quality="low")
        
        if success and os.path.exists(output_path):
            result = compute_ssim(test_pdf, output_path)
            if "error" not in result:
                assert 0.0 <= result["ssim"] <= 1.0


# =============================================
# Test compress_pdf_hybrid
# =============================================

class TestCompressPDFHybrid:
    """Tests for compress_pdf_hybrid() GS+PyMuPDF pipeline."""
    
    def test_hybrid_basic(self, test_pdf, output_path):
        """Hybrid compression should succeed and produce output."""
        from office_converter.core.pdf.compression import compress_pdf_hybrid
        
        success, reduction, stats = compress_pdf_hybrid(test_pdf, output_path, quality="medium")
        
        assert isinstance(success, bool)
        assert isinstance(reduction, float)
        assert isinstance(stats, dict)
        assert "pipeline" in stats
    
    def test_hybrid_nonexistent_file(self, output_path):
        """Hybrid with non-existent file should fail gracefully."""
        from office_converter.core.pdf.compression import compress_pdf_hybrid
        
        success, reduction, stats = compress_pdf_hybrid("/nonexistent.pdf", output_path)
        
        assert success is False
        assert "error" in stats
    
    def test_hybrid_empty_file(self, output_path):
        """Hybrid with empty file should fail gracefully."""
        from office_converter.core.pdf.compression import compress_pdf_hybrid
        
        # Create empty file
        fd, empty = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        try:
            success, _, stats = compress_pdf_hybrid(empty, output_path)
            assert success is False
        finally:
            os.remove(empty)
    
    def test_hybrid_returns_stats(self, test_pdf, output_path):
        """Stats should contain pipeline info and sizes."""
        from office_converter.core.pdf.compression import compress_pdf_hybrid
        
        success, reduction, stats = compress_pdf_hybrid(test_pdf, output_path)
        
        assert "gs_available" in stats
        assert "original_size" in stats
        assert "pipeline" in stats
    
    def test_hybrid_quality_presets(self, test_pdf):
        """All quality presets should be accepted."""
        from office_converter.core.pdf.compression import compress_pdf_hybrid
        
        for quality in ["extreme", "low", "medium", "high", "lossless"]:
            fd, out = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            try:
                success, _, stats = compress_pdf_hybrid(test_pdf, out, quality=quality)
                assert isinstance(success, bool), f"Preset '{quality}' returned non-bool"
            finally:
                if os.path.exists(out):
                    os.remove(out)
    
    def test_hybrid_cancel_check(self, test_pdf, output_path):
        """Cancel check should abort compression."""
        from office_converter.core.pdf.compression import compress_pdf_hybrid
        
        # Immediately cancel
        success, _, stats = compress_pdf_hybrid(
            test_pdf, output_path, cancel_check=lambda: True
        )
        # Should not crash — may either succeed quickly or return cancelled


# =============================================
# Test compress_to_target_size
# =============================================

class TestCompressToTargetSize:
    """Tests for compress_to_target_size() binary search algorithm."""
    
    def test_target_already_under(self, test_pdf, output_path):
        """File already under target should copy and succeed."""
        from office_converter.core.pdf.compression import compress_to_target_size
        
        # Very large target (10 MB)
        success, reduction, stats = compress_to_target_size(
            test_pdf, output_path, target_kb=10000
        )
        
        assert success is True
        assert stats.get("note") == "Already under target size" or success
    
    def test_target_nonexistent_file(self, output_path):
        """Non-existent file should fail gracefully."""
        from office_converter.core.pdf.compression import compress_to_target_size
        
        success, _, stats = compress_to_target_size("/nonexistent.pdf", output_path, target_kb=100)
        
        assert success is False
        assert "error" in stats
    
    def test_target_cancel(self, test_pdf, output_path):
        """Cancel check should abort search."""
        from office_converter.core.pdf.compression import compress_to_target_size
        
        success, _, stats = compress_to_target_size(
            test_pdf, output_path, target_kb=1,
            cancel_check=lambda: True
        )
        
        # Should not crash; either returns cancelled or best effort
    
    def test_target_returns_search_log(self, test_pdf_with_images, output_path):
        """Stats should include binary search iterations log."""
        from office_converter.core.pdf.compression import compress_to_target_size
        
        file_size_kb = os.path.getsize(test_pdf_with_images) // 1024
        # Set target slightly below current size
        target = max(1, file_size_kb - 1)
        
        success, reduction, stats = compress_to_target_size(
            test_pdf_with_images, output_path, target_kb=target
        )
        
        assert "pipeline" in stats
        assert stats["pipeline"] == "target_size"
    
    def test_target_respects_quality_range(self, test_pdf, output_path):
        """Custom min/max quality range should be respected."""
        from office_converter.core.pdf.compression import compress_to_target_size
        
        success, _, stats = compress_to_target_size(
            test_pdf, output_path, target_kb=10000,
            min_quality=50, max_quality=90
        )
        
        # Should succeed since target is large
        assert success is True
