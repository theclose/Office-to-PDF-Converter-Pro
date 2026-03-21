"""
PDF Page Management.
Handles rotation, extraction, deletion, and reordering of pages.
"""

import os
import shutil
from typing import List, Optional, Tuple

from .common import get_fitz, logger

def rotate_pages(input_path: str, output_path: str, rotation: int, page_indices: Optional[List[int]] = None) -> bool:
    """
    Rotate pages in a PDF.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if rotation not in [90, 180, 270]:
        logger.error(f"Invalid rotation: {rotation}. Must be 90, 180, or 270.")
        return False

    if not os.path.exists(input_path):
        return False

    try:
        doc = fitz.open(input_path)

        if page_indices is None:
            pages_to_rotate = range(len(doc))
        else:
            pages_to_rotate = [i for i in page_indices if 0 <= i < len(doc)]

        for page_idx in pages_to_rotate:
            page = doc[page_idx]
            page.set_rotation(page.rotation + rotation)

        doc.save(output_path)
        doc.close()

        logger.info(f"Rotated {len(list(pages_to_rotate))} pages by {rotation}°")
        return True

    except Exception as e:
        logger.error(f"Rotate pages error: {e}")
        return False


def parse_page_range(page_range_str: str, total_pages: Optional[int] = None) -> List[int]:
    """
    Parse page range string to list of 0-indexed page numbers.
    """
    if not page_range_str or not page_range_str.strip():
        return []
    
    pages = set()
    parts = page_range_str.replace(" ", "").split(",")

    for part in parts:
        if "-" in part:
            try:
                start, end = part.split("-", 1)
                start = max(1, int(start))
                end = int(end)
                if total_pages is not None:
                    end = min(total_pages, end)
                if start > end:
                    start, end = end, start
                for i in range(start, end + 1):
                    if i >= 1 and (total_pages is None or i <= total_pages):
                        pages.add(i - 1)
            except ValueError:
                continue
        else:
            try:
                page_num = int(part)
                if page_num >= 1 and (total_pages is None or page_num <= total_pages):
                    pages.add(page_num - 1)
            except ValueError:
                continue

    return sorted(list(pages))


def extract_pages(input_path: str, output_path: str, page_range: str) -> Tuple[bool, int]:
    """
    Extract specific pages from PDF to a new file.
    """
    fitz = get_fitz()
    if not fitz:
        return False, 0

    if not os.path.exists(input_path):
        return False, 0

    try:
        src_doc = fitz.open(input_path)
        page_indices = parse_page_range(page_range, len(src_doc))

        if not page_indices:
            logger.error("No valid pages to extract")
            src_doc.close()
            return False, 0

        new_doc = fitz.open()
        for idx in page_indices:
            new_doc.insert_pdf(src_doc, from_page=idx, to_page=idx)

        new_doc.save(output_path)
        new_doc.close()
        src_doc.close()

        logger.info(f"Extracted {len(page_indices)} pages")
        return True, len(page_indices)

    except Exception as e:
        logger.error(f"Extract pages error: {e}")
        return False, 0


def delete_pages(input_path: str, output_path: str, page_range: str) -> Tuple[bool, int]:
    """
    Delete specific pages from PDF.
    """
    fitz = get_fitz()
    if not fitz:
        return False, 0

    if not os.path.exists(input_path):
        return False, 0

    try:
        doc = fitz.open(input_path)
        page_indices = parse_page_range(page_range, len(doc))

        if not page_indices:
            logger.error("No valid pages to delete")
            doc.close()
            return False, 0

        if len(page_indices) >= len(doc):
            logger.error("Cannot delete all pages — would create empty PDF")
            doc.close()
            return False, 0

        for idx in sorted(page_indices, reverse=True):
            doc.delete_page(idx)

        doc.save(output_path)
        doc.close()

        logger.info(f"Deleted {len(page_indices)} pages")
        return True, len(page_indices)

    except Exception as e:
        logger.error(f"Delete pages error: {e}")
        return False, 0


def reorder_pages(input_path: str, output_path: str, new_order: List[int]) -> bool:
    """
    Reorder pages in a PDF.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if not os.path.exists(input_path):
        return False

    try:
        src_doc = fitz.open(input_path)

        total_pages = len(src_doc)
        if len(new_order) != total_pages:
            logger.error(f"new_order length ({len(new_order)}) != total pages ({total_pages})")
            src_doc.close()
            return False

        if set(new_order) != set(range(total_pages)):
            logger.error("new_order must contain each page index exactly once")
            src_doc.close()
            return False

        new_doc = fitz.open()
        for idx in new_order:
            new_doc.insert_pdf(src_doc, from_page=idx, to_page=idx)

        new_doc.save(output_path)
        new_doc.close()
        src_doc.close()

        logger.info(f"Reordered {total_pages} pages")
        return True

    except Exception as e:
        logger.error(f"Reorder pages error: {e}")
        return False


def reverse_pages(input_path: str, output_path: str) -> bool:
    """
    Reverse page order in a PDF.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if not os.path.exists(input_path):
        return False

    try:
        src_doc = fitz.open(input_path)
        new_order = list(range(len(src_doc) - 1, -1, -1))
        src_doc.close()

        return reorder_pages(input_path, output_path, new_order)

    except Exception as e:
        logger.error(f"Reverse pages error: {e}")
        return False


def extract_pdf_pages(pdf_path: str, page_indices: List[int]) -> bool:
    """
    Extract specific pages from PDF and overwrite the original.
    """
    fitz = get_fitz()
    if not fitz or not page_indices:
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
        logger.info(f"Extracted {len(valid_indices)} pages in-place")
        return True
    except Exception as e:
        logger.error(f"extract_pdf_pages failed: {e}")
        try:
            if os.path.exists(pdf_path + ".tmp"):
                os.remove(pdf_path + ".tmp")
        except OSError:
            pass
        return False
