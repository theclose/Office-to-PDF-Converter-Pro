"""
PDF Merging and Splitting operations.
"""

import os
from typing import List

from .common import get_fitz, logger

def merge_pdfs(pdf_paths: List[str], output_path: str) -> bool:
    """
    Merge multiple PDF files into one.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if not pdf_paths:
        return False

    try:
        merged_doc = fitz.open()

        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                doc = fitz.open(pdf_path)
                merged_doc.insert_pdf(doc)
                doc.close()
            else:
                logger.warning(f"Merge: skipping missing file: {pdf_path}")

        if len(merged_doc) == 0:
            merged_doc.close()
            return False

        merged_doc.save(output_path)
        merged_doc.close()

        logger.info(f"Merged {len(pdf_paths)} PDFs into {output_path}")
        return True

    except Exception as e:
        logger.error(f"Merge error: {e}")
        return False


def split_pdf(input_path: str, output_folder: str) -> bool:
    """
    Split a PDF into individual pages.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if not os.path.exists(input_path):
        return False

    try:
        os.makedirs(output_folder, exist_ok=True)

        doc = fitz.open(input_path)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        page_count = len(doc)

        for i in range(page_count):
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=i, to_page=i)

            output_path = os.path.join(output_folder, f"{base_name}_page_{i+1:03d}.pdf")
            new_doc.save(output_path)
            new_doc.close()

        doc.close()
        logger.info(f"Split PDF into {page_count} pages")
        return True

    except Exception as e:
        logger.error(f"Split error: {e}")
        return False
