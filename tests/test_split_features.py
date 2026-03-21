"""Tests for new split features: by_parts, by_pages_per_file."""
import os
import tempfile
import shutil
import pytest


# ─── Helpers ───
def _create_test_pdf(pages=10):
    """Create a minimal test PDF with specified number of pages."""
    try:
        import fitz
    except ImportError:
        pytest.skip("PyMuPDF not available")
    
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"Page {i+1} content", fontsize=14)
    
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def test_pdf_10():
    """Fixture: 10-page test PDF."""
    path = _create_test_pdf(pages=10)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def output_dir():
    """Fixture: temp output directory."""
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


# =============================================
# Test split_pdf_by_parts
# =============================================

class TestSplitByParts:
    """Tests for split_pdf_by_parts() — divide into N equal files."""
    
    def test_split_into_3_parts(self, test_pdf_10, output_dir):
        """10 pages ÷ 3 parts = files of 4+3+3 pages."""
        from office_converter.core.pdf.merge_split import split_pdf_by_parts
        
        success = split_pdf_by_parts(test_pdf_10, output_dir, num_parts=3)
        assert success is True
        
        # Should produce 3 output files
        files = sorted([f for f in os.listdir(output_dir) if f.endswith('.pdf')])
        assert len(files) == 3, f"Expected 3 files, got {len(files)}: {files}"
        
        # Verify page counts
        import fitz
        page_counts = []
        for f in files:
            doc = fitz.open(os.path.join(output_dir, f))
            page_counts.append(len(doc))
            doc.close()
        
        assert sum(page_counts) == 10, f"Total pages should be 10, got {sum(page_counts)}"
        assert page_counts[0] == 4  # ceil(10/3) = 4
    
    def test_split_into_1_part(self, test_pdf_10, output_dir):
        """1 part = entire document."""
        from office_converter.core.pdf.merge_split import split_pdf_by_parts
        
        success = split_pdf_by_parts(test_pdf_10, output_dir, num_parts=1)
        assert success is True
        
        files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
        assert len(files) == 1
        
        import fitz
        doc = fitz.open(os.path.join(output_dir, files[0]))
        assert len(doc) == 10
        doc.close()
    
    def test_split_parts_clamped_to_pages(self, test_pdf_10, output_dir):
        """num_parts > page_count should be clamped."""
        from office_converter.core.pdf.merge_split import split_pdf_by_parts
        
        success = split_pdf_by_parts(test_pdf_10, output_dir, num_parts=50)
        assert success is True
        
        files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
        # Should clamp to 10 parts (1 page each)
        assert len(files) == 10
    
    def test_split_parts_nonexistent_file(self, output_dir):
        """Non-existent file should return False."""
        from office_converter.core.pdf.merge_split import split_pdf_by_parts
        
        success = split_pdf_by_parts("/nonexistent.pdf", output_dir, num_parts=3)
        assert success is False
    
    def test_split_parts_naming(self, test_pdf_10, output_dir):
        """Output files should have part number and page range in name."""
        from office_converter.core.pdf.merge_split import split_pdf_by_parts
        
        split_pdf_by_parts(test_pdf_10, output_dir, num_parts=2)
        
        files = sorted(os.listdir(output_dir))
        # Should contain part_01 and part_02
        assert any("part_01" in f for f in files)
        assert any("part_02" in f for f in files)


# =============================================
# Test split_pdf_by_pages_per_file
# =============================================

class TestSplitByPagesPerFile:
    """Tests for split_pdf_by_pages_per_file() — N pages per chunk."""
    
    def test_split_5_pages_per_file(self, test_pdf_10, output_dir):
        """10 pages ÷ 5 per file = 2 files."""
        from office_converter.core.pdf.merge_split import split_pdf_by_pages_per_file
        
        success = split_pdf_by_pages_per_file(test_pdf_10, output_dir, pages_per_file=5)
        assert success is True
        
        files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
        assert len(files) == 2
        
        import fitz
        for f in files:
            doc = fitz.open(os.path.join(output_dir, f))
            assert len(doc) == 5
            doc.close()
    
    def test_split_3_pages_per_file_with_remainder(self, test_pdf_10, output_dir):
        """10 pages ÷ 3 per file = 3+3+3+1 pages = 4 files."""
        from office_converter.core.pdf.merge_split import split_pdf_by_pages_per_file
        
        success = split_pdf_by_pages_per_file(test_pdf_10, output_dir, pages_per_file=3)
        assert success is True
        
        files = sorted([f for f in os.listdir(output_dir) if f.endswith('.pdf')])
        assert len(files) == 4  # 3+3+3+1
        
        import fitz
        page_counts = []
        for f in files:
            doc = fitz.open(os.path.join(output_dir, f))
            page_counts.append(len(doc))
            doc.close()
        
        assert sum(page_counts) == 10
        assert page_counts[-1] == 1  # Remainder
    
    def test_split_pages_larger_than_total(self, test_pdf_10, output_dir):
        """pages_per_file > page_count = 1 file with all pages."""
        from office_converter.core.pdf.merge_split import split_pdf_by_pages_per_file
        
        success = split_pdf_by_pages_per_file(test_pdf_10, output_dir, pages_per_file=100)
        assert success is True
        
        files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
        assert len(files) == 1
    
    def test_split_1_page_per_file(self, test_pdf_10, output_dir):
        """1 page per file = same as original split_pdf."""
        from office_converter.core.pdf.merge_split import split_pdf_by_pages_per_file
        
        success = split_pdf_by_pages_per_file(test_pdf_10, output_dir, pages_per_file=1)
        assert success is True
        
        files = [f for f in os.listdir(output_dir) if f.endswith('.pdf')]
        assert len(files) == 10
    
    def test_split_pages_nonexistent_file(self, output_dir):
        """Non-existent file should return False."""
        from office_converter.core.pdf.merge_split import split_pdf_by_pages_per_file
        
        success = split_pdf_by_pages_per_file("/nonexistent.pdf", output_dir, pages_per_file=5)
        assert success is False
