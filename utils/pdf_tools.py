"""
PDF Tools - Utilities for PDF manipulation.
Uses PyMuPDF (fitz) for all operations.
"""

import os
import logging
import shutil
from typing import List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Check PyMuPDF availability
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("PyMuPDF not installed. PDF tools will be disabled.")


def post_process_pdf(pdf_path: str, password: str = None,
                     author: str = None, title: str = None) -> bool:
    """
    Apply password protection and/or metadata to PDF.
    
    Args:
        pdf_path: Path to PDF file
        password: Optional password for encryption
        author: Optional author metadata
        title: Optional title metadata
        
    Returns:
        True on success
    """
    if not HAS_PYMUPDF:
        return False

    try:
        doc = fitz.open(pdf_path)

        # Set metadata if provided
        if author or title:
            metadata = doc.metadata
            if author:
                metadata["author"] = author
            if title:
                metadata["title"] = title
            doc.set_metadata(metadata)

        # Create temp path
        temp_path = pdf_path + ".tmp"

        # Save with password or without
        if password:
            perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY
            doc.save(temp_path, encryption=fitz.PDF_ENCRYPT_AES_256,
                     user_pw=password, owner_pw=password, permissions=perm,
                     garbage=4, deflate=True)
        else:
            doc.save(temp_path, garbage=4, deflate=True)

        doc.close()

        # Replace original with temp
        shutil.move(temp_path, pdf_path)
        return True
    except Exception as e:
        logger.error(f"post_process_pdf failed: {e}")
        try:
            if os.path.exists(pdf_path + ".tmp"):
                os.remove(pdf_path + ".tmp")
        except Exception:
            pass
        return False


def rasterize_pdf(pdf_path: str, dpi: int = 150) -> bool:
    """
    Convert PDF pages to fully flattened images (rasterize) to prevent text/image extraction.
    Creates a true "scan-like" PDF where NOTHING can be extracted - all content becomes
    a single bitmap image per page.
    
    This is the NUCLEAR option for security:
    - Text cannot be selected/copied
    - Embedded images CANNOT be extracted as separate objects
    - Everything becomes a single rasterized image
    
    Args:
        pdf_path: Path to PDF file
        dpi: Resolution (higher = better quality but larger file)
             150 = good for documents
             200 = high quality
             300 = excellent (but large files)
        
    Returns:
        True on success
    """
    if not HAS_PYMUPDF:
        return False

    try:
        doc = fitz.open(pdf_path)
        new_doc = fitz.open()

        for page_num, page in enumerate(doc):
            # Render page to pixmap (bitmap)
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert to bytes - use JPEG for smaller size, PNG for quality
            # JPEG is much smaller but lossy
            # For security docs, use PNG to preserve quality
            img_format = "png"  # Change to "jpeg" for smaller files
            img_data = pix.tobytes(img_format)

            # Create new page with same dimensions
            # CRITICAL: Use original rect scaled by DPI
            page_rect = page.rect
            new_width = page_rect.width * (dpi / 72)
            new_height = page_rect.height * (dpi / 72)

            new_page = new_doc.new_page(width=new_width, height=new_height)

            # Insert image to cover entire page
            # This makes the image the ONLY content - nothing else exists
            img_rect = fitz.Rect(0, 0, new_width, new_height)

            # IMPORTANT: Use keep_proportion=False to force exact fit
            # This ensures no white borders or scaling issues
            new_page.insert_image(
                img_rect,
                stream=img_data,
                keep_proportion=False,
                overlay=True
            )

        doc.close()

        # Save with maximum compression
        temp_path = pdf_path + ".raster.tmp"
        new_doc.save(
            temp_path,
            garbage=4,           # Maximum garbage collection
            deflate=True,        # Compress streams
            clean=True,          # Remove unused objects
            pretty=False,        # Don't prettify (smaller)
            linear=False         # Don't linearize (web optimization not needed)
        )
        new_doc.close()

        # Replace original
        shutil.move(temp_path, pdf_path)
        return True

    except Exception as e:
        logger.error(f"rasterize_pdf failed: {e}")
        try:
            temp_path = pdf_path + ".raster.tmp"
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass
        return False


def parse_page_range(range_str: str) -> Optional[List[int]]:
    """
    Parse page range string like '1-3, 5, 7-10' into list of 0-indexed page numbers.
    
    Args:
        range_str: Range string (e.g., "1-3, 5, 7-10")
        
    Returns:
        List of 0-indexed page indices, or None if invalid/empty
    """
    if not range_str or not range_str.strip():
        return None

    pages = set()
    try:
        parts = range_str.replace(" ", "").split(",")
        for part in parts:
            if "-" in part:
                start, end = part.split("-", 1)
                start, end = int(start), int(end)
                if start > end:
                    start, end = end, start
                for p in range(start, end + 1):
                    if p >= 1:
                        pages.add(p - 1)
            else:
                p = int(part)
                if p >= 1:
                    pages.add(p - 1)
        return sorted(list(pages)) if pages else None
    except (ValueError, AttributeError):
        return None


def extract_pdf_pages(pdf_path: str, page_indices: List[int]) -> bool:
    """
    Extract specific pages from PDF and overwrite the original.
    
    Args:
        pdf_path: Path to PDF
        page_indices: List of 0-indexed page numbers
        
    Returns:
        True on success
    """
    if not HAS_PYMUPDF or not page_indices:
        return False

    try:
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count

        valid_indices = [i for i in page_indices if 0 <= i < total_pages]
        if not valid_indices:
            doc.close()
            return False

        new_doc = fitz.open()
        for idx in valid_indices:
            new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

        doc.close()

        temp_path = pdf_path + ".tmp"
        new_doc.save(temp_path, garbage=4, deflate=True)
        new_doc.close()

        shutil.move(temp_path, pdf_path)
        return True
    except Exception as e:
        logger.error(f"extract_pdf_pages failed: {e}")
        try:
            if os.path.exists(pdf_path + ".tmp"):
                os.remove(pdf_path + ".tmp")
        except Exception:
            pass
        return False


def merge_pdfs(pdf_files: List[str], output_path: str) -> Union[bool, str]:
    """
    Merge multiple PDF files into one.
    
    Args:
        pdf_files: List of PDF file paths (in order)
        output_path: Path for merged PDF
        
    Returns:
        True on success, error message string on failure
    """
    if not HAS_PYMUPDF:
        return "PyMuPDF not installed"

    if len(pdf_files) < 2:
        return "Need at least 2 PDF files to merge"

    try:
        merged = fitz.open()
        skipped = []

        for pdf_file in pdf_files:
            if not os.path.exists(pdf_file):
                skipped.append(f"{os.path.basename(pdf_file)} (not found)")
                continue

            try:
                doc = fitz.open(pdf_file)
                if doc.is_encrypted:
                    doc.close()
                    skipped.append(f"{os.path.basename(pdf_file)} (encrypted)")
                    continue

                for page_num in range(doc.page_count):
                    merged.insert_pdf(doc, from_page=page_num, to_page=page_num)
                doc.close()
            except Exception:
                skipped.append(f"{os.path.basename(pdf_file)} (error)")

        if merged.page_count == 0:
            return "No pages to merge. All files failed."

        merged.save(output_path, garbage=4, deflate=True)
        merged.close()

        if skipped:
            return f"Merged successfully but skipped: {', '.join(skipped)}"
        return True
    except Exception as e:
        return str(e)


def split_pdf(pdf_path: str, output_folder: str,
              mode: str = "each") -> Tuple[int, Optional[str]]:
    """
    Split PDF into multiple files.
    
    Args:
        pdf_path: Path to source PDF
        output_folder: Folder for output files
        mode: "each" = 1 page per file
        
    Returns:
        (success_count, error_message or None)
    """
    if not HAS_PYMUPDF:
        return (0, "PyMuPDF not installed")

    try:
        doc = fitz.open(pdf_path)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        count = 0

        if mode == "each":
            for i in range(doc.page_count):
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=i, to_page=i)
                output_name = f"{base_name}_page_{i+1}.pdf"
                output_path = os.path.join(output_folder, output_name)
                new_doc.save(output_path, garbage=4, deflate=True)
                new_doc.close()
                count += 1

        doc.close()
        return (count, None)
    except Exception as e:
        return (0, str(e))
