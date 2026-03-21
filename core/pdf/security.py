"""
PDF Security and Post-Processing.
Handles password protection, metadata manipulation, and rasterization (scan simulation).
"""

import os
import io
import shutil
import random

from .common import get_fitz, HAS_PIL, logger

try:
    from PIL import Image, ImageFilter
except ImportError:
    pass

def protect_pdf(input_path: str, output_path: str, password: str,
                owner_password: str = None) -> bool:
    """
    Add password protection to a PDF file.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if not os.path.exists(input_path):
        return False

    if not password:
        logger.error("Password cannot be empty")
        return False

    try:
        doc = fitz.open(input_path)

        if owner_password is None:
            owner_password = password

        perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY
        encrypt = fitz.PDF_ENCRYPT_AES_256

        doc.save(
            output_path,
            encryption=encrypt,
            owner_pw=owner_password,
            user_pw=password,
            permissions=perm
        )
        doc.close()

        logger.info(f"Protected PDF saved to {output_path}")
        return True

    except Exception as e:
        logger.error(f"Protect PDF error: {e}")
        return False


def post_process_pdf(pdf_path: str, password: str = None,
                     author: str = None, title: str = None) -> bool:
    """
    Apply password protection and/or metadata to PDF in-place.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    try:
        doc = fitz.open(pdf_path)

        if author or title:
            metadata = doc.metadata
            if author:
                metadata["author"] = author
            if title:
                metadata["title"] = title
            doc.set_metadata(metadata)

        temp_path = pdf_path + ".tmp"

        if password:
            perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY
            doc.save(temp_path, encryption=fitz.PDF_ENCRYPT_AES_256,
                     user_pw=password, owner_pw=password, permissions=perm,
                     garbage=4, deflate=True)
        else:
            doc.save(temp_path, garbage=4, deflate=True)

        doc.close()

        shutil.move(temp_path, pdf_path)
        return True
    except Exception as e:
        logger.error(f"post_process_pdf failed: {e}")
        try:
            if os.path.exists(pdf_path + ".tmp"):
                os.remove(pdf_path + ".tmp")
        except OSError:
            pass
        return False


def _apply_scan_effects(img):
    """Apply scan-like effects to PIL Image (internal helper)."""
    if not HAS_PIL:
        return img
        
    try:
        img = img.filter(ImageFilter.GaussianBlur(0.5))
        angle = random.uniform(-0.3, 0.3)
        img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor="white")
        return img
    except Exception as e:
        logger.error(f"Scan effect error: {e}")
        return img


def rasterize_pdf(pdf_path: str, output_path: str = None, dpi: int = 150, simulate_scan: bool = False) -> bool:
    """
    Convert PDF pages to fully flattened images (rasterize) to prevent extraction.
    Creates a true "scan-like" PDF.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    target_path = output_path if output_path else pdf_path
    
    try:
        doc = fitz.open(pdf_path)
        new_doc = fitz.open()
        
        page_count = len(doc)
        if page_count > 500:
            logger.warning(
                f"Large PDF detected ({page_count} pages). "
                "Consider splitting before rasterizing for better memory usage."
            )

        for page in doc:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            if simulate_scan and HAS_PIL:
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img = _apply_scan_effects(img)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80)
                img_data = buf.getvalue()
                buf.close()
                del img
            else:
                img_data = pix.tobytes("png")

            del pix

            page_rect = page.rect
            new_width = page_rect.width * (dpi / 72)
            new_height = page_rect.height * (dpi / 72)

            new_page = new_doc.new_page(width=new_width, height=new_height)
            img_rect = fitz.Rect(0, 0, new_width, new_height)
            new_page.insert_image(img_rect, stream=img_data,
                                  keep_proportion=False, overlay=True)
            
            del img_data

        doc.close()

        temp_path = target_path + ".raster.tmp"
        new_doc.save(temp_path, garbage=4, deflate=True, clean=True)
        new_doc.close()

        if os.path.exists(target_path) and target_path != temp_path:
            os.remove(target_path)
        shutil.move(temp_path, target_path)
        return True

    except Exception as e:
        logger.error(f"rasterize_pdf failed: {e}")
        try:
            temp_path = target_path + ".raster.tmp"
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return False
