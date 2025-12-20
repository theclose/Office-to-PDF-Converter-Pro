"""
LibreOffice Converter - Fallback converter when MS Office is not available.
Uses LibreOffice in headless mode for document conversion.

Requirements:
- LibreOffice must be installed (https://www.libreoffice.org/)
- soffice.exe must be in PATH or at default location
"""

import os
import subprocess
import logging
import shutil
from pathlib import Path
from typing import Optional, List

from .base import BaseConverter

logger = logging.getLogger(__name__)


def find_libreoffice() -> Optional[str]:
    """Find LibreOffice soffice executable."""
    # Common installation paths on Windows
    possible_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        r"C:\Program Files\LibreOffice 7\program\soffice.exe",
        r"C:\Program Files\LibreOffice 24\program\soffice.exe",
    ]

    # Check if soffice is in PATH
    soffice_in_path = shutil.which("soffice")
    if soffice_in_path:
        return soffice_in_path

    # Check common paths
    for path in possible_paths:
        if os.path.exists(path):
            return path

    # Search in Program Files
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    for base in [program_files, program_files_x86]:
        if os.path.exists(base):
            for folder in os.listdir(base):
                if folder.lower().startswith("libreoffice"):
                    soffice = os.path.join(base, folder, "program", "soffice.exe")
                    if os.path.exists(soffice):
                        return soffice

    return None


# Check if LibreOffice is available
LIBREOFFICE_PATH = find_libreoffice()
HAS_LIBREOFFICE = LIBREOFFICE_PATH is not None

if HAS_LIBREOFFICE:
    logger.info(f"LibreOffice found: {LIBREOFFICE_PATH}")
else:
    logger.info("LibreOffice not found. LibreOffice backend disabled.")


class LibreOfficeConverter(BaseConverter):
    """
    Converter using LibreOffice in headless mode.
    Works for Word, Excel, and PowerPoint files.
    """

    # Supports all Office formats
    SUPPORTED_EXTENSIONS: List[str] = [
        # Word
        ".doc", ".docx", ".docm", ".rtf", ".odt", ".txt",
        # Excel
        ".xls", ".xlsx", ".xlsm", ".xlsb", ".ods", ".csv",
        # PowerPoint
        ".ppt", ".pptx", ".pptm", ".ppsx", ".pps", ".odp",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._soffice_path = LIBREOFFICE_PATH

    def initialize(self) -> bool:
        """Check if LibreOffice is available."""
        if not self._soffice_path or not os.path.exists(self._soffice_path):
            logger.error("LibreOffice not found")
            return False
        return True

    def convert(self, input_path: str, output_path: str, quality: int = 100, **options) -> bool:
        """
        Convert document to PDF using LibreOffice.
        
        Args:
            input_path: Path to input document
            output_path: Path to output PDF
            quality: PDF quality (not directly used, LibreOffice uses its own settings)
            
        Returns:
            True if conversion successful
        """
        if not self._soffice_path:
            logger.error("LibreOffice not available")
            return False

        input_path = os.path.abspath(input_path)
        output_path = os.path.abspath(output_path)
        output_dir = os.path.dirname(output_path)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        try:
            # LibreOffice command for PDF conversion
            # --headless: Run without GUI
            # --convert-to pdf: Convert to PDF format
            # --outdir: Output directory
            cmd = [
                self._soffice_path,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", output_dir,
                input_path
            ]

            logger.info(f"LibreOffice converting: {os.path.basename(input_path)}")

            # Run conversion
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode != 0:
                logger.error(f"LibreOffice error: {result.stderr}")
                return False

            # LibreOffice outputs to same name with .pdf extension
            expected_output = os.path.join(
                output_dir,
                Path(input_path).stem + ".pdf"
            )

            # Rename if output path is different
            if expected_output != output_path:
                if os.path.exists(expected_output):
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    shutil.move(expected_output, output_path)

            if os.path.exists(output_path):
                logger.info(f"LibreOffice conversion successful: {os.path.basename(output_path)}")
                return True
            else:
                logger.error(f"Output file not created: {output_path}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("LibreOffice conversion timed out")
            return False
        except Exception as e:
            logger.error(f"LibreOffice conversion error: {e}")
            return False

    def cleanup(self):
        """No cleanup needed for LibreOffice."""
        pass


def is_libreoffice_available() -> bool:
    """Check if LibreOffice is available on this system."""
    return HAS_LIBREOFFICE


def get_libreoffice_version() -> Optional[str]:
    """Get LibreOffice version string."""
    if not LIBREOFFICE_PATH:
        return None

    try:
        result = subprocess.run(
            [LIBREOFFICE_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None
