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


def split_pdf_by_parts(input_path: str, output_folder: str, num_parts: int) -> bool:
    """Split a PDF into N roughly equal parts.
    
    Pages are distributed evenly. Example: 10 pages / 3 parts = 4+3+3.
    
    Args:
        input_path: Path to input PDF
        output_folder: Folder to save output files
        num_parts: Number of output files to create
    
    Returns:
        True if successful
    """
    import math
    
    fitz = get_fitz()
    if not fitz:
        return False
    
    if not os.path.exists(input_path):
        return False
    
    if num_parts < 1:
        logger.error(f"Invalid num_parts: {num_parts} (must be >= 1)")
        return False
    
    try:
        os.makedirs(output_folder, exist_ok=True)
        doc = fitz.open(input_path)
        page_count = len(doc)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        
        # Clamp num_parts
        num_parts = max(1, min(num_parts, page_count))
        
        # Calculate pages per part (distribute evenly)
        pages_per_part = math.ceil(page_count / num_parts)
        
        part_num = 0
        for start in range(0, page_count, pages_per_part):
            part_num += 1
            end = min(start + pages_per_part - 1, page_count - 1)
            
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end)
            
            output_path = os.path.join(
                output_folder,
                f"{base_name}_part_{part_num:02d}_p{start+1}-{end+1}.pdf"
            )
            new_doc.save(output_path)
            new_doc.close()
            
            logger.info(f"Split part {part_num}: pages {start+1}-{end+1}")
        
        doc.close()
        logger.info(f"Split PDF into {part_num} parts ({page_count} pages)")
        return True
    
    except Exception as e:
        logger.error(f"Split by parts error: {e}")
        return False


def split_pdf_by_pages_per_file(input_path: str, output_folder: str, pages_per_file: int) -> bool:
    """Split a PDF into chunks of N pages each.
    
    Args:
        input_path: Path to input PDF
        output_folder: Folder to save output files
        pages_per_file: Number of pages per output file
    
    Returns:
        True if successful
    """
    fitz = get_fitz()
    if not fitz:
        return False
    
    if not os.path.exists(input_path):
        return False
    
    try:
        os.makedirs(output_folder, exist_ok=True)
        doc = fitz.open(input_path)
        page_count = len(doc)
        base_name = os.path.splitext(os.path.basename(input_path))[0]
        
        pages_per_file = max(1, pages_per_file)
        
        part_num = 0
        for start in range(0, page_count, pages_per_file):
            part_num += 1
            end = min(start + pages_per_file - 1, page_count - 1)
            
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start, to_page=end)
            
            output_path = os.path.join(
                output_folder,
                f"{base_name}_part_{part_num:02d}_p{start+1}-{end+1}.pdf"
            )
            new_doc.save(output_path)
            new_doc.close()
        
        doc.close()
        logger.info(f"Split PDF into {part_num} files ({pages_per_file} pages each)")
        return True
    
    except Exception as e:
        logger.error(f"Split by pages error: {e}")
        return False

