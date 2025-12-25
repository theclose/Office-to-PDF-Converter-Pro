"""
PDF Tools - Utilities for PDF manipulation.
Re-exports from core.pdf_tools for backward compatibility.

DEPRECATED: Import from office_converter.core.pdf_tools instead.
"""

import logging

logger = logging.getLogger(__name__)

# Re-export everything from core.pdf_tools for backward compatibility
try:
    from office_converter.core.pdf_tools import (
        # Constants
        HAS_PYMUPDF,
        # Merge/Split
        merge_pdfs,
        split_pdf,
        # Compress/Protect
        compress_pdf,
        protect_pdf,
        post_process_pdf,
        rasterize_pdf,
        # Watermark
        add_watermark,
        # Images
        pdf_to_images,
        images_to_pdf,
        # Page operations
        parse_page_range,
        extract_pages,
        extract_pdf_pages,
        delete_pages,
        rotate_pages,
        reorder_pages,
        reverse_pages,
    )
    
except ImportError as e:
    logger.error(f"Failed to import from core.pdf_tools: {e}")
    HAS_PYMUPDF = False
    
    # Fallback: define HAS_PYMUPDF directly
    try:
        import fitz
        HAS_PYMUPDF = True
    except ImportError:
        pass


# Make all functions available for import
__all__ = [
    "HAS_PYMUPDF",
    "merge_pdfs",
    "split_pdf",
    "compress_pdf",
    "protect_pdf",
    "post_process_pdf",
    "rasterize_pdf",
    "add_watermark",
    "pdf_to_images",
    "images_to_pdf",
    "parse_page_range",
    "extract_pages",
    "extract_pdf_pages",
    "delete_pages",
    "rotate_pages",
    "reorder_pages",
    "reverse_pages",
]
