"""Pytest configuration and fixtures."""
import os
import sys
import pytest

# Add package root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a minimal PDF for testing (requires pymupdf)."""
    try:
        import fitz
        pdf_path = tmp_path / "test.pdf"
        doc = fitz.open()
        doc.new_page()
        doc.save(str(pdf_path))
        doc.close()
        return str(pdf_path)
    except ImportError:
        pytest.skip("PyMuPDF not installed")
