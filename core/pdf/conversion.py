"""
PDF to Images and Images to PDF conversion.
"""

import os
from typing import List, Tuple, Dict, Any

from .common import get_fitz, HAS_PIL, logger

try:
    from PIL import Image
except ImportError:
    pass

def pdf_to_images(
    input_path: str,
    output_folder: str,
    dpi: int = 150,
    image_format: str = "png"
) -> List[str]:
    """Convert PDF pages to images."""
    fitz = get_fitz()
    if not fitz or not os.path.exists(input_path):
        return []

    try:
        os.makedirs(output_folder, exist_ok=True)
        doc = fitz.open(input_path)
        base_name = os.path.splitext(os.path.basename(input_path))[0]

        created_files = []
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)

        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            ext = "png" if image_format.lower() == "png" else "jpg"
            out_path = os.path.join(output_folder, f"{base_name}_page_{i+1:03d}.{ext}")

            if ext == "jpg":
                pix.save(out_path, output="jpeg", jpg_quality=90)
            else:
                pix.save(out_path)

            created_files.append(out_path)

        doc.close()
        return created_files

    except Exception as e:
        logger.error(f"PDF to images error: {e}")
        return []


def pdf_to_single_image(
    input_path: str,
    output_path: str,
    dpi: int = 150,
    image_format: str = "png",
    page_gap: int = 10,
    background_color: tuple = (255, 255, 255),
    progress_callback: callable = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Convert all PDF pages to a single combined image (vertically stacked).
    """
    fitz = get_fitz()
    if not fitz or not HAS_PIL:
        logger.error("PyMuPDF or PIL not available")
        return False, {"error": "Missing dependencies"}
    
    if not os.path.exists(input_path):
        return False, {"error": "File not found"}
    
    stats = {
        "pages": 0,
        "width": 0,
        "height": 0,
        "file_size": 0
    }
    
    try:
        doc = fitz.open(input_path)
        page_count = doc.page_count
        stats["pages"] = page_count
        
        if page_count == 0:
            doc.close()
            return False, {"error": "PDF has no pages"}
        
        if page_count > 100:
            logger.warning(f"Large PDF with {page_count} pages - may use significant memory")
        
        zoom = dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        
        logger.info(f"Phase 1: Calculating dimensions for {page_count} pages...")
        page_images = []
        max_width = 0
        total_height = 0
        
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            page_images.append(img)
            max_width = max(max_width, pix.width)
            total_height += pix.height
            pix = None
            if progress_callback:
                progress_callback(i + 1, page_count * 2, (i + 1) / (page_count * 2))
        
        total_height += (page_count - 1) * page_gap
        
        logger.info(f"Combined image size: {max_width}x{total_height} pixels")
        stats["width"] = max_width
        stats["height"] = total_height
        
        logger.info("Phase 2: Creating combined image...")
        combined = Image.new("RGB", (max_width, total_height), background_color)
        
        y_offset = 0
        for i, img in enumerate(page_images):
            x_offset = (max_width - img.width) // 2
            combined.paste(img, (x_offset, y_offset))
            y_offset += img.height + page_gap
            page_images[i] = None
            if progress_callback:
                progress_callback(page_count + i + 1, page_count * 2, 
                                (page_count + i + 1) / (page_count * 2))
        
        page_images = None
        
        logger.info(f"Phase 3: Saving to {output_path}...")
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        if image_format.lower() == "jpg" or image_format.lower() == "jpeg":
            combined.save(output_path, "JPEG", quality=90, optimize=True)
        else:
            combined.save(output_path, "PNG", optimize=True)
        
        if os.path.exists(output_path):
            stats["file_size"] = os.path.getsize(output_path)
        
        doc.close()
        
        logger.info(f"✅ Combined {page_count} pages into single image: {stats['file_size'] // 1024} KB")
        return True, stats
        
    except Exception as e:
        logger.error(f"PDF to single image error: {e}")
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}


def images_to_pdf(image_paths: List[str], output_path: str) -> bool:
    """Combine multiple images into a single PDF."""
    fitz = get_fitz()
    if not fitz or not image_paths:
        return False

    try:
        doc = fitz.open()

        for img_path in image_paths:
            if not os.path.exists(img_path):
                continue

            img = fitz.open(img_path)
            pdf_bytes = img.convert_to_pdf()
            img.close()

            img_pdf = fitz.open("pdf", pdf_bytes)
            doc.insert_pdf(img_pdf)
            img_pdf.close()

        if len(doc) == 0:
            return False

        doc.save(output_path)
        doc.close()
        return True

    except Exception as e:
        logger.error(f"Images to PDF error: {e}")
        return False
