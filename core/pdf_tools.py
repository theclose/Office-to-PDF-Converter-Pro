"""
PDF Tools Facade Module.
Re-exports functionalities from the core.pdf sub-package.
"""

from office_converter.core.pdf.common import get_fitz, HAS_PYMUPDF, HAS_PIL
from office_converter.core.pdf.compression import (
    compress_pdf, compress_pdf_advanced, analyze_pdf_content, compress_pdf_smart, estimate_compression,
    compress_to_target_size, compute_ssim, compress_pdf_hybrid,
)
from office_converter.core.pdf.conversion import (
    pdf_to_images, pdf_to_single_image, images_to_pdf
)
from office_converter.core.pdf.merge_split import (
    merge_pdfs, split_pdf
)
from office_converter.core.pdf.pages import (
    rotate_pages, parse_page_range, extract_pages, delete_pages, reorder_pages, reverse_pages, extract_pdf_pages
)
from office_converter.core.pdf.security import (
    protect_pdf, post_process_pdf, rasterize_pdf, _apply_scan_effects
)
from office_converter.core.pdf.watermark import (
    add_watermark
)

# Maintain backward compatibility with the lazy loading private API
def _get_fitz():
    """Lazy import fitz (PyMuPDF) on first use."""
    return get_fitz()

__all__ = [
    'HAS_PYMUPDF', 'HAS_PIL', '_get_fitz',
    'compress_pdf', 'compress_pdf_advanced', 'analyze_pdf_content', 'compress_pdf_smart', 'estimate_compression',
    'pdf_to_images', 'pdf_to_single_image', 'images_to_pdf',
    'merge_pdfs', 'split_pdf',
    'rotate_pages', 'parse_page_range', 'extract_pages', 'delete_pages', 'reorder_pages', 'reverse_pages', 'extract_pdf_pages',
    'protect_pdf', 'post_process_pdf', 'rasterize_pdf', '_apply_scan_effects',
    'add_watermark'
]
