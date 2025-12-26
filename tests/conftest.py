"""
Enhanced Pytest Configuration - Military-Grade Fixtures

Comprehensive test infrastructure with:
- COM object mocking
- Worker process simulation
- System resource mocking (psutil)
- Hypothesis strategies
- Temporary file management
"""

import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, MagicMock
from multiprocessing import Queue

# Add package root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# FIXTURES: COM Mocking
# ============================================================================

@pytest.fixture
def mock_com_object():
    """Mock Word/Excel/PowerPoint COM object.
    
    Simulates Office automation without requiring installation.
    """
    mock_app = MagicMock()
    
    # Mock document
    mock_doc = MagicMock()
    mock_doc.ExportAsFixedFormat = MagicMock(return_value=True)
    mock_doc.Close = MagicMock()
    mock_doc.Name = "test.docx"
    
    # Mock workbook
    mock_workbook = MagicMock()
    mock_workbook.ExportAsFixedFormat = MagicMock(return_value=True)
    mock_workbook.Close = MagicMock()
    
    # Wire up
    mock_app.Documents = MagicMock()
    mock_app.Documents.Open = MagicMock(return_value=mock_doc)
    mock_app.Workbooks = MagicMock()
    mock_app.Workbooks.Open = MagicMock(return_value=mock_workbook)
    mock_app.Quit = MagicMock()
    
    mock_app._mock_doc = mock_doc
    mock_app._mock_workbook = mock_workbook
    
    return mock_app


# ============================================================================
# FIXTURES: Worker Process Mocking
# ============================================================================

@pytest.fixture
def mock_worker():
    """Mock WorkerProcess with queues."""
    worker = MagicMock()
    
    worker.task_queue = MagicMock(spec=Queue)
    worker.result_queue = MagicMock(spec=Queue)
    worker.pid = 12345
    worker.is_alive = MagicMock(return_value=True)
    worker.start = MagicMock()
    worker.terminate = MagicMock()
    worker.kill = MagicMock()
    
    def terminate_effect():
        worker.is_alive.return_value = False
    
    worker.terminate.side_effect = terminate_effect
    worker.kill.side_effect = terminate_effect
    
    return worker


# ============================================================================
# FIXTURES: System Resource Mocking (psutil)
# ============================================================================

@pytest.fixture
def mock_psutil(mocker):
    """Mock psutil for system monitoring."""
    mock_vm = MagicMock()
    mock_vm.available = 4 * 1024 * 1024 * 1024  # 4 GB
    mock_vm.percent = 50.0
    
    mock_process = MagicMock()
    mock_memory_info = MagicMock()
    mock_memory_info.rss = 100 * 1024 * 1024  # 100 MB
    mock_process.memory_info.return_value = mock_memory_info
    mock_process.is_running.return_value = True
    mock_process.pid = 12345
    
    mocker.patch('psutil.virtual_memory', return_value=mock_vm)
    mocker.patch('psutil.Process', return_value=mock_process)
    
    return (mock_vm, mock_process)


# ============================================================================
# FIXTURES: Temporary Directories
# ============================================================================

@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory."""
    return tmp_path


@pytest.fixture
def sample_pdf(tmp_path):
    """Create a minimal PDF for testing."""
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


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "property: Property-based tests with Hypothesis")
    config.addinivalue_line("markers", "resilience: Failure handling tests")
    config.addinivalue_line("markers", "integration: Multi-component integration tests")
    config.addinivalue_line("markers", "slow: Tests taking >1 second")


# ============================================================================
# HYPOTHESIS STRATEGIES
# ============================================================================

from hypothesis import strategies as st

# File sizes (1 KB to 100 MB)
file_size_strategy = st.integers(min_value=1024, max_value=100 * 1024 * 1024)

# Timeouts (0.1s to 600s)
timeout_strategy = st.floats(min_value=0.1, max_value=600.0, allow_nan=False, allow_infinity=False)

# Memory (100 MB to 16 GB)
memory_strategy = st.integers(min_value=100 * 1024 * 1024, max_value=16 * 1024 * 1024 * 1024)

# Filenames (valid Windows)
filename_strategy = st.text(
    alphabet=st.characters(blacklist_categories=('Cc', 'Cs'), blacklist_characters='\\/:*?"<>|'),
    min_size=1,
    max_size=100
).map(lambda s: s.strip() or "file")
