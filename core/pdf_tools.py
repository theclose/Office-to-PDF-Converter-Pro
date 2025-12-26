"""
PDF Tools Module - Professional PDF Compression, Watermark, PDF↔Images
Based on PyMuPDF best practices from official documentation.
"""

import os
import logging
import shutil
from typing import List, Optional, Tuple

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from PIL import Image, ImageFilter, ImageEnhance, ImageChops
    import random
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

logger = logging.getLogger(__name__)


# =============================================================================
# MERGE PDFs
# =============================================================================

def merge_pdfs(pdf_paths: List[str], output_path: str) -> bool:
    """
    Merge multiple PDF files into one.
    
    Args:
        pdf_paths: List of PDF file paths to merge
        output_path: Path for output merged PDF
        
    Returns:
        Success status
    """
    if not HAS_PYMUPDF:
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


# =============================================================================
# SPLIT PDF
# =============================================================================

def split_pdf(input_path: str, output_folder: str) -> bool:
    """
    Split a PDF into individual pages.
    
    Args:
        input_path: Path to input PDF
        output_folder: Folder to save individual page PDFs
        
    Returns:
        Success status
    """
    if not HAS_PYMUPDF:
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


# =============================================================================
# PROTECT PDF - Password Protection
# =============================================================================

def protect_pdf(input_path: str, output_path: str, password: str,
                owner_password: str = None) -> bool:
    """
    Add password protection to a PDF file.
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output protected PDF
        password: User password (required to open)
        owner_password: Owner password (for editing permissions), defaults to user password
        
    Returns:
        Success status
    """
    if not HAS_PYMUPDF:
        return False

    if not os.path.exists(input_path):
        return False

    if not password:
        logger.error("Password cannot be empty")
        return False

    try:
        doc = fitz.open(input_path)

        # Use owner password same as user password if not specified
        if owner_password is None:
            owner_password = password

        # Set encryption
        perm = fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY  # Allow print and copy
        encrypt = fitz.PDF_ENCRYPT_AES_256  # Strong encryption

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


# =============================================================================
# POST-PROCESS PDF - Metadata and Password
# =============================================================================

def post_process_pdf(pdf_path: str, password: str = None,
                     author: str = None, title: str = None) -> bool:
    """
    Apply password protection and/or metadata to PDF in-place.
    
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
        except OSError:
            pass
        return False


# =============================================================================
# RASTERIZE PDF - Flatten to Images
# =============================================================================

def _apply_scan_effects(img):
    """Apply scan-like effects to PIL Image (internal helper)."""
    if not HAS_PIL:
        return img
        
    try:
        # 1. Slight Blur (soften digital edges)
        img = img.filter(ImageFilter.GaussianBlur(0.5))
        
        # 2. Slight Skew/Rotate (-0.3 to 0.3 degrees)
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
    
    Args:
        pdf_path: Path to source PDF file
        output_path: Path to save result (if None, overwrites source)
        dpi: Resolution (150=good, 200=high, 300=excellent)
        simulate_scan: If True, adds noise, blur, grayscale and rotation to mimic real scanner
        
    Returns:
        True on success
    """
    if not HAS_PYMUPDF:
        return False

    target_path = output_path if output_path else pdf_path
    
    try:
        doc = fitz.open(pdf_path)
        new_doc = fitz.open()
        
        # P3 Performance: Warn for very large PDFs
        page_count = len(doc)
        if page_count > 500:
            logger.warning(
                f"Large PDF detected ({page_count} pages). "
                "Consider splitting before rasterizing for better memory usage."
            )

        for page in doc:
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Apply effects if requested
            if simulate_scan and HAS_PIL:
                # Convert to PIL
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                # Apply effects
                img = _apply_scan_effects(img)
                # Convert back to bytes (JPEG with compression)
                # Use standard IO to get bytes
                import io
                buf = io.BytesIO()
                # Save as JPEG with 80 quality for scan artifact
                img.save(buf, format="JPEG", quality=80)
                img_data = buf.getvalue()
                buf.close()  # P3: Release buffer memory
                del img  # P3: Explicit cleanup
            else:
                img_data = pix.tobytes("png")

            # P3: Release pixmap memory immediately after use
            del pix

            page_rect = page.rect
            new_width = page_rect.width * (dpi / 72)
            new_height = page_rect.height * (dpi / 72)

            new_page = new_doc.new_page(width=new_width, height=new_height)
            img_rect = fitz.Rect(0, 0, new_width, new_height)
            new_page.insert_image(img_rect, stream=img_data,
                                  keep_proportion=False, overlay=True)
            
            # P3: Release image data after insertion
            del img_data

        doc.close()

        # Save to temp then move/rename
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
            temp_path = pdf_path + ".raster.tmp"
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except OSError:
            pass
        return False


# =============================================================================
# COMPRESS PDF - Professional Implementation
# Based on PyMuPDF official documentation and best practices
# =============================================================================

def compress_pdf(input_path: str, output_path: str, quality: str = "medium") -> Tuple[bool, float]:
    """
    Compress a PDF file using multiple optimization techniques:
    1. Garbage collection (remove unused objects)
    2. Stream compression (deflate)
    3. Font subsetting (only embed used glyphs)
    4. Metadata cleanup (scrub)
    5. Image rewriting (optional, for aggressive compression)
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF  
        quality: 
            - "low": Maximum compression (may reduce image quality)
            - "medium": Balanced compression (recommended)
            - "high": Minimal compression (preserve quality)
        
    Returns:
        Tuple of (success, compression_percentage)
    """
    # Validate PyMuPDF
    if not HAS_PYMUPDF:
        logger.error("PyMuPDF (fitz) not installed")
        return False, 0.0

    # Validate input file
    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return False, 0.0

    original_size = os.path.getsize(input_path)
    if original_size == 0:
        logger.error("Input file is empty")
        return False, 0.0

    logger.info(f"Starting compression: {input_path}")
    logger.info(f"Original size: {original_size / 1024:.1f} KB")

    try:
        # Open PDF
        doc = fitz.open(input_path)

        if doc.page_count == 0:
            logger.error("PDF has no pages")
            doc.close()
            return False, 0.0

        # ========================================
        # STEP 1: Remove metadata and dead weight
        # ========================================
        try:
            doc.scrub(
                attached_files=True,
                clean_pages=True,
                embedded_files=True,
                hidden_text=True,
                javascript=True,
                metadata=True,
                redact_images=0,
                redactions=True,
                remove_links=False,
                reset_fields=True,
                reset_responses=True,
                thumbnails=True,
                xml_metadata=True,
            )
            logger.info("Step 1: Metadata removed")
        except Exception as e:
            logger.warning(f"Scrub failed (continuing): {e}")

        # ========================================
        # STEP 2: Subset fonts (only used glyphs)
        # ========================================
        try:
            doc.subset_fonts()
            logger.info("Step 2: Fonts subsetted")
        except Exception as e:
            logger.warning(f"Font subset failed (continuing): {e}")

        # ========================================
        # STEP 3: Quality-based settings
        # ========================================
        quality_settings = {
            "low": {
                "garbage": 4,      # Maximum garbage collection + merge duplicates
                "deflate": True,   # Compress all streams
                "clean": True,     # Clean content streams
            },
            "medium": {
                "garbage": 3,      # Good garbage collection
                "deflate": True,
                "clean": True,
            },
            "high": {
                "garbage": 2,      # Light garbage collection
                "deflate": True,
                "clean": True,
            },
        }
        settings = quality_settings.get(quality, quality_settings["medium"])
        logger.info(f"Step 3: Using {quality} quality settings (garbage={settings['garbage']})")

        # ========================================
        # STEP 4: Save with compression
        # ========================================
        doc.save(
            output_path,
            garbage=settings["garbage"],
            deflate=settings["deflate"],
            clean=settings["clean"],
            pretty=False,          # Don't pretty-print (smaller)
            no_new_id=True,        # Keep same ID
        )
        doc.close()
        logger.info("Step 4: Saved with compression")

        # ========================================
        # STEP 5: Verify and compare
        # ========================================
        if not os.path.exists(output_path):
            logger.error("Output file was not created")
            return False, 0.0

        new_size = os.path.getsize(output_path)

        # If result is larger, use original
        if new_size >= original_size:
            logger.info("Compression did not reduce size - copying original")
            shutil.copy(input_path, output_path)
            return True, 0.0

        # Calculate reduction percentage
        reduction = ((original_size - new_size) / original_size) * 100
        logger.info(f"Success: {original_size/1024:.1f}KB → {new_size/1024:.1f}KB ({reduction:.1f}% reduced)")

        return True, reduction

    except Exception as e:
        logger.error(f"Compression failed: {e}")
        import traceback
        traceback.print_exc()
        return False, 0.0


# =============================================================================
# WATERMARK PDF
# =============================================================================

def add_watermark(
    input_path: str,
    output_path: str,
    text: str,
    opacity: float = 0.3,
    font_size: int = 60,
    color: Tuple[float, float, float] = (0.7, 0.7, 0.7),
    rotation: int = 0  # Only 0, 90, 180, 270 are valid
) -> bool:
    """Add text watermark to all pages of a PDF."""
    if not HAS_PYMUPDF:
        return False

    if not os.path.exists(input_path):
        return False

    # Validate rotation (only 0, 90, 180, 270 are valid for insert_text)
    if rotation not in [0, 90, 180, 270]:
        rotation = 0

    try:
        doc = fitz.open(input_path)

        for page in doc:
            rect = page.rect
            cx, cy = rect.width / 2, rect.height / 2
            text_width = len(text) * font_size * 0.4

            page.insert_text(
                point=(cx - text_width / 2, cy),
                text=text,
                fontsize=font_size,
                fontname="helv",
                color=color,
                rotate=rotation,
                overlay=True,
            )

        doc.save(output_path)
        doc.close()
        return True

    except Exception as e:
        logger.error(f"Watermark error: {e}")
        return False


# =============================================================================
# PDF TO IMAGES
# =============================================================================

def pdf_to_images(
    input_path: str,
    output_folder: str,
    dpi: int = 150,
    image_format: str = "png"
) -> List[str]:
    """Convert PDF pages to images."""
    if not HAS_PYMUPDF or not os.path.exists(input_path):
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


# =============================================================================
# IMAGES TO PDF
# =============================================================================

def images_to_pdf(image_paths: List[str], output_path: str) -> bool:
    """Combine multiple images into a single PDF."""
    if not HAS_PYMUPDF or not image_paths:
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


# =============================================================================
# PAGE MANAGEMENT - Phase 1
# =============================================================================

def rotate_pages(input_path: str, output_path: str, rotation: int, page_indices: Optional[List[int]] = None) -> bool:
    """
    Rotate pages in a PDF.
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        rotation: Rotation angle (90, 180, or 270)
        page_indices: List of 0-indexed pages to rotate. None = all pages.
        
    Returns:
        Success status
    """
    if not HAS_PYMUPDF:
        return False

    if rotation not in [90, 180, 270]:
        logger.error(f"Invalid rotation: {rotation}. Must be 90, 180, or 270.")
        return False

    if not os.path.exists(input_path):
        return False

    try:
        doc = fitz.open(input_path)

        # Determine which pages to rotate
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
    
    Args:
        page_range_str: String like "1-5,7,10-15" (1-indexed)
        total_pages: Optional total number of pages (for validation). 
                     If None, pages are not clamped to a maximum.
        
    Returns:
        List of 0-indexed page numbers, or empty list if invalid
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
                    start, end = end, start  # Handle reversed ranges
                for i in range(start, end + 1):
                    if i >= 1 and (total_pages is None or i <= total_pages):
                        pages.add(i - 1)  # Convert to 0-indexed
            except ValueError:
                continue
        else:
            try:
                page_num = int(part)
                if page_num >= 1 and (total_pages is None or page_num <= total_pages):
                    pages.add(page_num - 1)  # Convert to 0-indexed
            except ValueError:
                continue

    return sorted(list(pages))


def extract_pages(input_path: str, output_path: str, page_range: str) -> Tuple[bool, int]:
    """
    Extract specific pages from PDF to a new file.
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        page_range: Page range string like "1-5,7,10-15" (1-indexed)
        
    Returns:
        Tuple of (success, number of pages extracted)
    """
    if not HAS_PYMUPDF:
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
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        page_range: Page range string like "1-5,7,10-15" (1-indexed)
        
    Returns:
        Tuple of (success, number of pages deleted)
    """
    if not HAS_PYMUPDF:
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

        # Delete in reverse order to maintain correct indices
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
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        new_order: List of 0-indexed page numbers in new order
                   e.g., [2,0,1,3] moves page 3 to first position
        
    Returns:
        Success status
    """
    if not HAS_PYMUPDF:
        return False

    if not os.path.exists(input_path):
        return False

    try:
        src_doc = fitz.open(input_path)

        # Validate new_order
        total_pages = len(src_doc)
        if len(new_order) != total_pages:
            logger.error(f"new_order length ({len(new_order)}) != total pages ({total_pages})")
            src_doc.close()
            return False

        if set(new_order) != set(range(total_pages)):
            logger.error("new_order must contain each page index exactly once")
            src_doc.close()
            return False

        # Create new document with pages in new order
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
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        
    Returns:
        Success status
    """
    if not HAS_PYMUPDF:
        return False

    if not os.path.exists(input_path):
        return False

    try:
        src_doc = fitz.open(input_path)
        new_order = list(range(len(src_doc) - 1, -1, -1))  # Reverse order
        src_doc.close()

        return reorder_pages(input_path, output_path, new_order)

    except Exception as e:
        logger.error(f"Reverse pages error: {e}")
        return False


# =============================================================================
# EXTRACT PDF PAGES (IN-PLACE) - For converter post-processing
# =============================================================================

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
