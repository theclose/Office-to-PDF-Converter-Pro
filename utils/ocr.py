"""
OCR Module - Optical Character Recognition for scanned PDFs.
Uses Tesseract OCR to make scanned PDFs searchable.

Requirements:
- Tesseract OCR must be installed (https://github.com/UB-Mannheim/tesseract/wiki)
- pytesseract Python package
- pdf2image Python package (requires poppler)
"""

import os
import logging
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

# Check dependencies
HAS_TESSERACT = False
HAS_PDF2IMAGE = False
TESSERACT_PATH = None

# Try to import pytesseract
try:
    import pytesseract
    
    # Find Tesseract executable
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Tesseract-OCR\tesseract.exe",
    ]
    
    # Check if tesseract is in PATH
    tesseract_in_path = shutil.which("tesseract")
    if tesseract_in_path:
        TESSERACT_PATH = tesseract_in_path
        pytesseract.pytesseract.tesseract_cmd = tesseract_in_path
        HAS_TESSERACT = True
    else:
        for path in possible_paths:
            if os.path.exists(path):
                TESSERACT_PATH = path
                pytesseract.pytesseract.tesseract_cmd = path
                HAS_TESSERACT = True
                break
    
    if HAS_TESSERACT:
        logger.info(f"Tesseract OCR found: {TESSERACT_PATH}")
    else:
        logger.warning("Tesseract executable not found")
        
except ImportError:
    logger.warning("pytesseract not installed. OCR will be disabled.")

# Try to import pdf2image
try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
    logger.info("pdf2image available")
except ImportError:
    logger.warning("pdf2image not installed. PDF OCR will be disabled.")

# Check PyMuPDF for PDF creation
try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logger.warning("PyMuPDF not installed. OCR PDF creation will be limited.")


def is_ocr_available() -> bool:
    """Check if OCR is available."""
    return HAS_TESSERACT and (HAS_PDF2IMAGE or HAS_PYMUPDF)


def get_tesseract_languages() -> List[str]:
    """Get list of installed Tesseract languages."""
    if not HAS_TESSERACT:
        return []
    
    try:
        langs = pytesseract.get_languages()
        return [l for l in langs if l != 'osd']
    except Exception:
        return ['eng', 'vie']  # Default fallback


def ocr_image(image_path: str, lang: str = 'eng+vie') -> str:
    """
    Perform OCR on an image file.
    
    Args:
        image_path: Path to image file
        lang: Tesseract language code(s)
        
    Returns:
        Extracted text
    """
    if not HAS_TESSERACT:
        raise RuntimeError("Tesseract OCR not available")
    
    try:
        text = pytesseract.image_to_string(image_path, lang=lang)
        return text
    except Exception as e:
        logger.error(f"OCR error: {e}")
        raise


def ocr_pdf_to_searchable(
    input_pdf: str, 
    output_pdf: str, 
    lang: str = 'eng+vie',
    dpi: int = 300,
    progress_callback=None
) -> bool:
    """
    Convert a scanned PDF to a searchable PDF with OCR text layer.
    
    Args:
        input_pdf: Path to input scanned PDF
        output_pdf: Path to output searchable PDF
        lang: Tesseract language code(s), e.g., 'eng', 'vie', 'eng+vie'
        dpi: Resolution for image conversion
        progress_callback: Optional callback for progress updates
        
    Returns:
        True if successful
    """
    if not is_ocr_available():
        logger.error("OCR not available")
        return False
    
    input_pdf = os.path.abspath(input_pdf)
    output_pdf = os.path.abspath(output_pdf)
    
    try:
        # Method 1: Using PyMuPDF (faster, better quality)
        if HAS_PYMUPDF:
            return _ocr_with_pymupdf(input_pdf, output_pdf, lang, dpi, progress_callback)
        
        # Method 2: Using pdf2image + pytesseract PDF output
        elif HAS_PDF2IMAGE:
            return _ocr_with_pdf2image(input_pdf, output_pdf, lang, dpi, progress_callback)
        
        else:
            logger.error("No OCR method available")
            return False
            
    except Exception as e:
        logger.error(f"OCR PDF error: {e}")
        return False


def _ocr_with_pymupdf(
    input_pdf: str, 
    output_pdf: str, 
    lang: str,
    dpi: int,
    progress_callback
) -> bool:
    """OCR using PyMuPDF for image extraction and PDF creation."""
    try:
        doc = fitz.open(input_pdf)
        total_pages = len(doc)
        
        # Create new PDF with text layer
        new_doc = fitz.open()
        
        for page_num in range(total_pages):
            if progress_callback:
                progress_callback((page_num + 1) / total_pages)
            
            page = doc[page_num]
            
            # Render page to image
            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # Save to temp file for OCR
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                pix.save(tmp_path)
            
            try:
                # Perform OCR
                ocr_data = pytesseract.image_to_pdf_or_hocr(
                    tmp_path, 
                    lang=lang, 
                    extension='pdf'
                )
                
                # Insert OCR page
                ocr_doc = fitz.open("pdf", ocr_data)
                new_doc.insert_pdf(ocr_doc)
                ocr_doc.close()
                
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        # Save result
        new_doc.save(output_pdf, garbage=4, deflate=True)
        new_doc.close()
        doc.close()
        
        logger.info(f"OCR complete: {total_pages} pages processed")
        return True
        
    except Exception as e:
        logger.error(f"PyMuPDF OCR error: {e}")
        return False


def _ocr_with_pdf2image(
    input_pdf: str, 
    output_pdf: str, 
    lang: str,
    dpi: int,
    progress_callback
) -> bool:
    """OCR using pdf2image for conversion."""
    try:
        # Convert PDF to images
        logger.info(f"Converting PDF to images at {dpi} DPI...")
        images = convert_from_path(input_pdf, dpi=dpi)
        total_pages = len(images)
        
        # Process each page
        pdf_pages = []
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, image in enumerate(images):
                if progress_callback:
                    progress_callback((i + 1) / total_pages)
                
                # Save image
                img_path = os.path.join(tmp_dir, f"page_{i:04d}.png")
                image.save(img_path, "PNG")
                
                # OCR to PDF
                pdf_data = pytesseract.image_to_pdf_or_hocr(
                    img_path, 
                    lang=lang, 
                    extension='pdf'
                )
                
                pdf_path = os.path.join(tmp_dir, f"page_{i:04d}.pdf")
                with open(pdf_path, 'wb') as f:
                    f.write(pdf_data)
                
                pdf_pages.append(pdf_path)
            
            # Merge all pages
            if HAS_PYMUPDF:
                final_doc = fitz.open()
                for pdf_path in pdf_pages:
                    page_doc = fitz.open(pdf_path)
                    final_doc.insert_pdf(page_doc)
                    page_doc.close()
                final_doc.save(output_pdf, garbage=4, deflate=True)
                final_doc.close()
            else:
                # Fallback: just copy first page (limited)
                if pdf_pages:
                    shutil.copy(pdf_pages[0], output_pdf)
        
        logger.info(f"OCR complete: {total_pages} pages processed")
        return True
        
    except Exception as e:
        logger.error(f"pdf2image OCR error: {e}")
        return False


def extract_text_from_pdf(pdf_path: str, lang: str = 'eng+vie') -> str:
    """
    Extract text from a PDF using OCR.
    
    Args:
        pdf_path: Path to PDF file
        lang: Tesseract language code(s)
        
    Returns:
        Extracted text from all pages
    """
    if not is_ocr_available():
        raise RuntimeError("OCR not available")
    
    if not HAS_PYMUPDF:
        raise RuntimeError("PyMuPDF required for PDF text extraction")
    
    try:
        doc = fitz.open(pdf_path)
        all_text = []
        
        for page in doc:
            # Get pixmap
            pix = page.get_pixmap(dpi=150)
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                pix.save(tmp_path)
            
            try:
                text = pytesseract.image_to_string(tmp_path, lang=lang)
                all_text.append(text)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        doc.close()
        return "\n\n".join(all_text)
        
    except Exception as e:
        logger.error(f"PDF text extraction error: {e}")
        raise


# Status info
def get_ocr_status() -> dict:
    """Get OCR module status."""
    return {
        "available": is_ocr_available(),
        "tesseract_path": TESSERACT_PATH,
        "has_tesseract": HAS_TESSERACT,
        "has_pdf2image": HAS_PDF2IMAGE,
        "has_pymupdf": HAS_PYMUPDF,
        "languages": get_tesseract_languages() if HAS_TESSERACT else [],
    }
