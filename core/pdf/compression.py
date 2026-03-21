"""
PDF Compression Module.
Professional implementation with hybrid pipeline:
  - Ghostscript (lossy image compression, Bicubic + sRGB)
  - PyMuPDF (lossless structure optimization)
  - Smart image type detection (photo/diagram/B&W)
  - Progressive JPEG + Adaptive DPI
"""

import os
import io
import shutil
import math
from typing import Tuple, Dict, Any, Optional

from .common import get_fitz, HAS_PIL, logger

try:
    from PIL import Image, ImageStat
except ImportError:
    pass

# Lazy import GS support
def _get_gs_support():
    try:
        from .ghostscript import find_ghostscript, hybrid_compress, HAS_GS
        find_ghostscript()  # trigger auto-detect
        return HAS_GS, hybrid_compress
    except ImportError:
        return False, None


# ============================================================
# Image type detection + Adaptive DPI helpers
# ============================================================

def _detect_image_type(pil_img) -> str:
    """Classify image type for optimal compression strategy.
    
    Returns:
        'photo' - Natural photograph (many gradients, use JPEG)
        'diagram' - Diagram/chart/screenshot (few colors, use PNG/Flate)
        'bw' - Black & white (use CCITT or skip)
    """
    if not HAS_PIL:
        return "photo"  # default
    
    # B&W detection
    if pil_img.mode == "1":
        return "bw"
    if pil_img.mode == "L":
        # Grayscale: check if mostly black/white
        stat = ImageStat.Stat(pil_img)
        if stat.stddev[0] > 100:  # High contrast B&W
            extremes = pil_img.getextrema()
            if extremes == (0, 255):
                hist = pil_img.histogram()
                # If >80% pixels are near black or white
                bw_pixels = sum(hist[:32]) + sum(hist[224:])
                total = sum(hist)
                if total > 0 and bw_pixels / total > 0.80:
                    return "bw"
    
    # Convert to RGB for analysis
    if pil_img.mode not in ("RGB", "L"):
        try:
            analysis_img = pil_img.convert("RGB")
        except Exception:
            return "photo"
    else:
        analysis_img = pil_img
    
    # Sample unique colors (faster than full count for large images)
    try:
        # Resize to small thumbnail for fast analysis
        thumb = analysis_img.copy()
        thumb.thumbnail((100, 100))
        unique_colors = len(set(thumb.getdata()))
        
        # Diagram detection: few unique colors + sharp edges
        if unique_colors < 256:
            return "diagram"
        
        # Photo detection: many colors, smooth gradients
        stat = ImageStat.Stat(analysis_img)
        avg_stddev = sum(stat.stddev) / len(stat.stddev)
        if avg_stddev > 40:  # High color variation = photo
            return "photo"
        elif unique_colors < 1000:
            return "diagram"
        else:
            return "photo"
    except Exception:
        return "photo"


def _calc_adaptive_dpi(pil_img, rect_width_pts: float, rect_height_pts: float, target_dpi: int) -> int:
    """Calculate optimal DPI based on actual render size.
    
    Avoids unnecessary upsampling of already-small images.
    
    Args:
        pil_img: Source PIL image
        rect_width_pts: Width of image rect on page (in PDF points, 1pt = 1/72 inch)
        rect_height_pts: Height of image rect on page
        target_dpi: Maximum desired DPI
    
    Returns:
        Optimal DPI (may be lower than target if image is small)
    """
    if rect_width_pts <= 0 or rect_height_pts <= 0:
        return target_dpi
    
    # Calculate current effective DPI
    width_inches = rect_width_pts / 72.0
    height_inches = rect_height_pts / 72.0
    
    current_dpi_w = pil_img.width / width_inches if width_inches > 0 else target_dpi
    current_dpi_h = pil_img.height / height_inches if height_inches > 0 else target_dpi
    current_dpi = min(current_dpi_w, current_dpi_h)
    
    # Don't upsample: if image already at or below target, keep it
    if current_dpi <= target_dpi * 1.1:  # 10% margin
        return int(current_dpi)
    
    return target_dpi


def _compress_image_smart(
    pil_img, 
    img_type: str, 
    jpeg_quality: int, 
    max_dim: int,
    rect=None,
    target_dpi: int = 150,
) -> Optional[bytes]:
    """Compress a single image using optimal strategy based on type.
    
    Returns compressed bytes, or None if compression not beneficial.
    """
    original_size = 0
    
    # Calculate adaptive DPI if rect available
    if rect and hasattr(rect, 'width'):
        adaptive_dpi = _calc_adaptive_dpi(pil_img, rect.width, rect.height, target_dpi)
        # Recalculate max_dim based on adaptive DPI
        max_dim = int(adaptive_dpi * 11.69)  # A4 width in inches
    
    # Color mode conversion
    if pil_img.mode in ("RGBA", "P", "LA"):
        pil_img = pil_img.convert("RGB")
    elif pil_img.mode == "CMYK":
        pil_img = pil_img.convert("RGB")
    elif pil_img.mode not in ("RGB", "L", "1"):
        pil_img = pil_img.convert("RGB")
    
    # Resize if needed
    if pil_img.width > max_dim or pil_img.height > max_dim:
        ratio = min(max_dim / pil_img.width, max_dim / pil_img.height)
        new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
        pil_img = pil_img.resize(new_size, Image.LANCZOS)
    
    buffer = io.BytesIO()
    
    if img_type == "bw":
        # B&W: keep as-is (already optimally compressed in PDF)
        # Or convert to 1-bit and save as PNG
        if pil_img.mode != "1":
            pil_img = pil_img.convert("1")
        pil_img.save(buffer, "PNG", optimize=True)
    elif img_type == "diagram":
        # Diagrams: PNG (Flate) preserves sharp edges better than JPEG
        if pil_img.mode == "1":
            pil_img = pil_img.convert("RGB")
        pil_img.save(buffer, "PNG", optimize=True)
    else:
        # Photos: JPEG with progressive encoding
        if pil_img.mode == "1":
            pil_img = pil_img.convert("RGB")
        elif pil_img.mode == "L":
            pass  # JPEG supports grayscale
        pil_img.save(
            buffer, "JPEG",
            quality=jpeg_quality,
            optimize=True,
            progressive=True,  # Progressive JPEG: ~2-5% smaller + web-friendly
        )
    
    return buffer.getvalue()

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
    fitz = get_fitz()
    if not fitz:
        logger.error("PyMuPDF (fitz) not installed")
        return False, 0.0

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


# Quality presets for compression
COMPRESSION_PRESETS = {
    "low": {
        "dpi": 120,         # Increased from 72 - text needs higher DPI
        "jpeg_quality": 60,  # Increased from 50
        "description": "Strong compression (good for images, readable text)",
        "expected_reduction": "70-85%"
    },
    "medium": {
        "dpi": 150,
        "jpeg_quality": 75,
        "description": "Balanced compression (recommended)",
        "expected_reduction": "50-70%"
    },
    "high": {
        "dpi": 200,
        "jpeg_quality": 85,
        "description": "Quality preserve (minimal visual loss)",
        "expected_reduction": "30-50%"
    },
    "extreme": {
        "dpi": 96,           # Increased from 72 - minimum for readable text
        "jpeg_quality": 45,  # Increased from 30
        "grayscale": True,
        "description": "Extreme compression (grayscale, some quality loss)",
        "expected_reduction": "80-90%"
    },
    "lossless": {
        "dpi": None,  # No image resampling
        "jpeg_quality": None,  # No recompression
        "description": "Lossless (only metadata/font optimization)",
        "expected_reduction": "10-20%"
    }
}


def compress_pdf_advanced(
    input_path: str,
    output_path: str,
    quality: str = "medium",
    target_dpi: int = None,
    jpeg_quality: int = None,
    grayscale: bool = False,
    remove_images: bool = False,
    progress_callback: callable = None,
    cancel_check: callable = None,
) -> Tuple[bool, float, Dict[str, Any]]:
    """Advanced PDF compression with hybrid pipeline.
    
    Pipeline selection:
      1. If Ghostscript available + image-heavy PDF → GS hybrid pipeline
      2. Otherwise → PyMuPDF + smart image compression (PIL)
    
    Improvements over basic compress:
      - Auto image type detection (photo→JPEG, diagram→PNG, B&W→skip)
      - Progressive JPEG encoding (~2-5% smaller)
      - Adaptive DPI (no upsampling of small images)
      - Ghostscript hybrid pipeline when available
    """
    fitz = get_fitz()
    if not fitz:
        logger.error("PyMuPDF (fitz) not installed")
        return False, 0.0, {"error": "PyMuPDF not installed"}
    
    if not HAS_PIL:
        logger.warning("PIL not installed - image optimization disabled")
    
    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return False, 0.0, {"error": "File not found"}
    
    original_size = os.path.getsize(input_path)
    if original_size == 0:
        logger.error("Input file is empty")
        return False, 0.0, {"error": "Empty file"}
    
    preset = COMPRESSION_PRESETS.get(quality, COMPRESSION_PRESETS["medium"])
    target_dpi = target_dpi or preset.get("dpi")
    jpeg_quality = jpeg_quality or preset.get("jpeg_quality")
    grayscale = grayscale or preset.get("grayscale", False)
    
    logger.info(f"Starting advanced compression: {input_path}")
    logger.info(f"Original size: {original_size / 1024:.1f} KB")
    logger.info(f"Preset: {quality} (DPI={target_dpi}, JPEG={jpeg_quality}%)")
    
    stats = {
        "original_size": original_size,
        "preset": quality,
        "target_dpi": target_dpi,
        "jpeg_quality": jpeg_quality,
        "grayscale": grayscale,
        "images_found": 0,
        "images_optimized": 0,
        "images_skipped": 0,
        "images_photo": 0,
        "images_diagram": 0,
        "images_bw": 0,
        "fonts_subsetted": False,
        "metadata_removed": False,
        "pipeline": "pymupdf",
    }
    
    # === TRY GHOSTSCRIPT HYBRID PIPELINE (for non-lossless, non-custom) ===
    if quality not in ("lossless", "custom") and not remove_images and target_dpi and jpeg_quality:
        has_gs, gs_hybrid = _get_gs_support()
        if has_gs and gs_hybrid:
            # Analyze PDF to decide if GS pipeline is beneficial
            analysis = analyze_pdf_content(input_path)
            image_ratio = len(analysis.get("image_pages", [])) / max(analysis.get("total_pages", 1), 1)
            
            if image_ratio > 0.3 or analysis.get("total_image_bytes", 0) > 1_000_000:
                logger.info(f"Image-heavy PDF detected ({image_ratio:.0%} image pages) → using GS hybrid pipeline")
                try:
                    gs_ok, gs_reduction, gs_pipeline = gs_hybrid(
                        input_path, output_path, dpi=target_dpi
                    )
                    if gs_ok and gs_reduction > 0:
                        new_size = os.path.getsize(output_path)
                        stats["new_size"] = new_size
                        stats["reduction_percent"] = gs_reduction
                        stats["saved_bytes"] = original_size - new_size
                        stats["pipeline"] = gs_pipeline
                        logger.info(f"GS hybrid success: {gs_reduction:.1f}% reduced via {gs_pipeline}")
                        return True, gs_reduction, stats
                except Exception as e:
                    logger.warning(f"GS hybrid failed, falling back to PyMuPDF: {e}")
    
    try:
        doc = fitz.open(input_path)
        
        if doc.page_count == 0:
            logger.error("PDF has no pages")
            doc.close()
            return False, 0.0, {"error": "No pages"}
        
        stats["page_count"] = doc.page_count
        
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
            stats["metadata_removed"] = True
            logger.info("Phase 1: Metadata removed")
        except Exception as e:
            logger.warning(f"Scrub failed: {e}")
        
        try:
            doc.subset_fonts()
            stats["fonts_subsetted"] = True
            logger.info("Phase 2: Fonts subsetted")
        except Exception as e:
            logger.warning(f"Font subset failed: {e}")
        
        if target_dpi and jpeg_quality and not remove_images and quality != "lossless":
            logger.info(f"Phase 3: Smart image compression (DPI={target_dpi}, Quality={jpeg_quality}%)")
            
            max_dim = int(target_dpi * 11.69)
            
            image_tasks = []
            xref_data = {}
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                images = page.get_images(full=True)
                for img_info in images:
                    xref = img_info[0]
                    stats["images_found"] += 1
                    try:
                        rects = page.get_image_rects(xref)
                        if rects:
                            image_tasks.append((page_num, xref, rects[0]))
                    except Exception:
                        pass
            
            for page_num, xref, rect in image_tasks:
                if xref in xref_data:
                    continue
                if cancel_check and cancel_check():
                    doc.close()
                    return False, 0.0, {"error": "Cancelled", "cancelled": True}
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        continue
                    image_bytes = base_image["image"]
                    original_img_size = len(image_bytes)
                    # Skip tiny images (<10KB) and icons (<100px)
                    if original_img_size < 10000 or not HAS_PIL:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        continue
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    if pil_img.width <= 100 and pil_img.height <= 100:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        pil_img = None
                        continue
                    
                    if grayscale:
                        pil_img = pil_img.convert("L")
                    
                    # Auto-detect image type for optimal compression
                    img_type = _detect_image_type(pil_img)
                    stats[f"images_{img_type}"] = stats.get(f"images_{img_type}", 0) + 1
                    
                    # Skip B&W images (already well-compressed in PDF)
                    if img_type == "bw" and quality != "low":
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        pil_img = None
                        continue
                    
                    # Use smart compression with type detection + adaptive DPI
                    compressed = _compress_image_smart(
                        pil_img, img_type, jpeg_quality, max_dim,
                        rect=rect, target_dpi=target_dpi
                    )
                    
                    if compressed and len(compressed) < original_img_size * 0.9:
                        xref_data[xref] = compressed
                        stats["images_optimized"] += 1
                    else:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                    pil_img = None
                except Exception as e:
                    logger.warning(f"Could not process image {xref}: {e}")
                    xref_data[xref] = None
                    stats["images_skipped"] += 1
            
            current_progress = 0
            total_tasks = len(image_tasks)
            replaced_xrefs = set()
            for page_num, xref, rect in image_tasks:
                current_progress += 1
                compressed = xref_data.get(xref)
                if compressed is None or xref in replaced_xrefs:
                    continue
                replaced_xrefs.add(xref)
                try:
                    page = doc[page_num]
                    page.delete_image(xref)
                    page.insert_image(rect, stream=compressed)
                except Exception as e:
                    logger.warning(f"Could not replace image on page {page_num+1}: {e}")
                if progress_callback and total_tasks > 0:
                    progress_callback(current_progress, total_tasks, current_progress / total_tasks)
            
            logger.info(f"Phase 3 complete: {stats['images_optimized']}/{stats['images_found']} images compressed")
        
        elif not remove_images and quality == "lossless":
            logger.info("Phase 3: Lossless mode - skipping image recompression")
        
        elif remove_images:
            logger.info("Phase 3: Removing all images")
            for page_num in range(doc.page_count):
                page = doc[page_num]
                for img in page.get_images():
                    xref = img[0]
                    try:
                        # Safe removal: delete_image properly cleans up xref
                        # NEVER use update_stream() for this (see known-trap #11)
                        page.delete_image(xref)
                        stats["images_optimized"] += 1
                    except Exception:
                        pass
        
        logger.info("Phase 4: Saving optimized PDF...")
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True,
            pretty=False,
            no_new_id=True
        )
        doc.close()
        
        if not os.path.exists(output_path):
            return False, 0.0, {"error": "Output file not created"}
        
        new_size = os.path.getsize(output_path)
        stats["new_size"] = new_size
        
        if new_size >= original_size:
            shutil.copy(input_path, output_path)
            logger.info("Compression made file larger, keeping original")
            stats["new_size"] = original_size
            stats["reduction_percent"] = 0.0
            return True, 0.0, stats
        
        reduction = ((original_size - new_size) / original_size) * 100
        stats["reduction_percent"] = reduction
        stats["saved_bytes"] = original_size - new_size
        
        logger.info(f"✅ Success: {original_size/1024:.1f}KB → {new_size/1024:.1f}KB ({reduction:.1f}% reduced)")
        logger.info(f"   Images optimized: {stats['images_optimized']}/{stats['images_found']}")
        
        return True, reduction, stats
        
    except Exception as e:
        logger.error(f"Advanced compression failed: {e}")
        import traceback
        traceback.print_exc()
        return False, 0.0, {"error": str(e)}


def analyze_pdf_content(input_path: str) -> Dict[str, Any]:
    """Analyze PDF content for optimal compression strategy.
    
    Returns detailed breakdown: page types, image formats, font data,
    compressibility score, and recommended compression method.
    """
    fitz = get_fitz()
    if not fitz or not os.path.exists(input_path):
        return {"error": "File not found or PyMuPDF not available"}
    
    try:
        doc = fitz.open(input_path)
        file_size = os.path.getsize(input_path)
        
        analysis = {
            "total_pages": doc.page_count,
            "file_size": file_size,
            "text_pages": [],
            "image_pages": [],
            "mixed_pages": [],
            "total_images": 0,
            "total_image_bytes": 0,
            "has_text": False,
            # New: format breakdown
            "image_formats": {},  # e.g. {"jpeg": 5, "png": 2}
            "font_count": 0,
            "font_bytes_est": 0,
            # New: compressibility score
            "compressibility": 0.0,  # 0-1 scale
            "gs_available": False,
        }
        
        # Check GS availability
        has_gs, _ = _get_gs_support()
        analysis["gs_available"] = has_gs
        
        seen_xrefs = set()
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            images = page.get_images(full=True)
            image_count = len(images)
            text = page.get_text("text").strip()
            has_text = len(text) > 50
            
            for img in images:
                xref = img[0]
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                try:
                    base_img = doc.extract_image(xref)
                    if base_img:
                        img_bytes = len(base_img.get("image", b""))
                        analysis["total_image_bytes"] += img_bytes
                        # Track format
                        fmt = base_img.get("ext", "unknown")
                        analysis["image_formats"][fmt] = analysis["image_formats"].get(fmt, 0) + 1
                except Exception:
                    pass
            
            analysis["total_images"] += image_count
            
            if image_count == 0 and has_text:
                analysis["text_pages"].append(page_num)
            elif image_count > 0 and not has_text:
                analysis["image_pages"].append(page_num)
            else:
                analysis["mixed_pages"].append(page_num)
            
            if has_text:
                analysis["has_text"] = True
        
        # Font analysis
        try:
            fonts = set()
            for page_num in range(min(doc.page_count, 10)):  # Sample first 10 pages
                page = doc[page_num]
                for font in page.get_fonts():
                    fonts.add(font[3])  # font name
            analysis["font_count"] = len(fonts)
            # Rough estimate: avg embedded font ~100KB
            analysis["font_bytes_est"] = len(fonts) * 100_000
        except Exception:
            pass
        
        doc.close()
        
        # Calculate compressibility score (0-1)
        image_ratio = analysis["total_image_bytes"] / max(file_size, 1)
        if image_ratio > 0.7:
            analysis["compressibility"] = 0.85  # Very compressible (image-heavy)
        elif image_ratio > 0.3:
            analysis["compressibility"] = 0.60  # Moderately compressible
        elif analysis["font_count"] > 3:
            analysis["compressibility"] = 0.30  # Some font savings possible
        else:
            analysis["compressibility"] = 0.15  # Mostly text, low compressibility
        
        # Recommendation
        if len(analysis["image_pages"]) == analysis["total_pages"]:
            analysis["recommendation"] = "rasterize"
        elif len(analysis["text_pages"]) == analysis["total_pages"]:
            analysis["recommendation"] = "lossless"
        elif image_ratio > 0.5 and has_gs:
            analysis["recommendation"] = "hybrid"  # GS + PyMuPDF
        else:
            analysis["recommendation"] = "smart"
        
        return analysis
        
    except Exception as e:
        logger.error(f"PDF analysis failed: {e}")
        return {"error": str(e)}


def compress_pdf_smart(
    input_path: str,
    output_path: str,
    quality: str = "medium",
    progress_callback: callable = None
) -> Tuple[bool, float, Dict[str, Any]]:
    fitz = get_fitz()
    if not fitz or not HAS_PIL:
        return False, 0.0, {"error": "PyMuPDF or PIL not available"}
    
    if not os.path.exists(input_path):
        return False, 0.0, {"error": "File not found"}
    
    QUALITY_SETTINGS = {
        "low": {"jpeg_quality": 50, "max_dim": 1200},
        "medium": {"jpeg_quality": 75, "max_dim": 1600},
        "high": {"jpeg_quality": 90, "max_dim": 2400},
    }
    settings = QUALITY_SETTINGS.get(quality, QUALITY_SETTINGS["medium"])
    original_size = os.path.getsize(input_path)
    stats = {
        "original_size": original_size,
        "images_found": 0,
        "images_optimized": 0,
        "images_skipped": 0,
        "images_photo": 0,
        "images_diagram": 0,
        "images_bw": 0,
        "text_preserved": True,
        "bytes_saved_images": 0,
        "method": "smart_selective",
        "pipeline": "pymupdf_smart",
    }
    
    try:
        doc = fitz.open(input_path)
        logger.info(f"Smart compression: {doc.page_count} pages, quality={quality}")
        
        logger.info("Phase 1: Metadata cleanup...")
        try:
            doc.scrub(redact_images=0, garbage=4)
        except Exception:
            pass
        
        logger.info("Phase 2: Font subsetting...")
        try:
            doc.subset_fonts()
        except Exception:
            pass
        
        logger.info("Phase 3: Selective image compression...")
        total_images = 0
        for pg in doc:
            total_images += len(pg.get_images(full=True))
        current_image = 0
        
        image_tasks = []
        xref_data = {}
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            images = page.get_images(full=True)
            
            for img_info in images:
                xref = img_info[0]
                try:
                    rects = page.get_image_rects(xref)
                    if rects:
                        image_tasks.append((page_num, xref, rects[0]))
                except Exception:
                    pass
                
                if xref in xref_data:
                    continue
                
                stats["images_found"] += 1
                current_image += 1
                
                if progress_callback and total_images > 0:
                    progress_callback(current_image, total_images, current_image / total_images)
                
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        xref_data[xref] = None
                        continue
                    
                    image_bytes = base_image["image"]
                    original_img_size = len(image_bytes)
                    
                    if original_img_size < 5000:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        continue
                    
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    
                    # Skip very small images (icons, bullets)
                    if pil_img.width <= 100 and pil_img.height <= 100:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        pil_img = None
                        continue
                    
                    # Auto-detect image type
                    img_type = _detect_image_type(pil_img)
                    stats[f"images_{img_type}"] = stats.get(f"images_{img_type}", 0) + 1
                    
                    # Skip B&W in high quality mode
                    if img_type == "bw" and quality == "high":
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        pil_img = None
                        continue
                    
                    # Use smart compression with type detection
                    max_dim = settings["max_dim"]
                    compressed_bytes = _compress_image_smart(
                        pil_img, img_type, settings["jpeg_quality"], max_dim,
                        rect=None, target_dpi=150
                    )
                    
                    if compressed_bytes and len(compressed_bytes) < original_img_size * 0.9:
                        xref_data[xref] = (compressed_bytes, original_img_size)
                        stats["images_optimized"] += 1
                        stats["bytes_saved_images"] += original_img_size - len(compressed_bytes)
                    else:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                    
                    pil_img = None
                        
                except Exception as e:
                    logger.warning(f"Could not process image {xref}: {e}")
                    xref_data[xref] = None
                    stats["images_skipped"] += 1
        
        replaced_xrefs = set()
        for page_num, xref, rect in image_tasks:
            data = xref_data.get(xref)
            if data is None or xref in replaced_xrefs:
                continue
            replaced_xrefs.add(xref)
            compressed_bytes, _ = data
            try:
                page = doc[page_num]
                page.delete_image(xref)
                page.insert_image(rect, stream=compressed_bytes)
            except Exception as e:
                logger.warning(f"Could not replace image on page {page_num+1}: {e}")
        
        logger.info("Phase 4: Saving optimized PDF...")
        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            clean=True,
            pretty=False,
            no_new_id=True
        )
        doc.close()
        
        if not os.path.exists(output_path):
            return False, 0.0, {"error": "Output file not created"}
        
        new_size = os.path.getsize(output_path)
        stats["new_size"] = new_size
        
        if new_size >= original_size:
            shutil.copy(input_path, output_path)
            logger.info("Compression made file larger, keeping original")
            return True, 0.0, stats
        
        reduction = ((original_size - new_size) / original_size) * 100
        stats["reduction_percent"] = reduction
        stats["saved_bytes"] = original_size - new_size
        
        logger.info(f"✅ Smart Success: {original_size//1024}KB → {new_size//1024}KB ({reduction:.1f}% smaller)")
        logger.info(f"   Images: {stats['images_optimized']}/{stats['images_found']} "
                    f"(photo:{stats.get('images_photo',0)} diagram:{stats.get('images_diagram',0)} bw:{stats.get('images_bw',0)})")
        
        return True, reduction, stats
        
    except Exception as e:
        logger.error(f"Smart compression failed: {e}")
        return False, 0.0, {"error": str(e)}


def estimate_compression(input_path: str, quality: str = "medium") -> Dict[str, Any]:
    """Estimate compression results using actual PDF analysis."""
    if not os.path.exists(input_path):
        return {"error": "File not found"}
    
    original_size = os.path.getsize(input_path)
    
    # Try actual analysis for better estimates
    analysis = analyze_pdf_content(input_path)
    compressibility = analysis.get("compressibility", 0.5)
    
    # Adjust estimate based on quality preset and actual content
    quality_factors = {
        "low": 0.85,       # Low quality = aggressive = high reduction
        "medium": 0.70,
        "high": 0.50,
        "extreme": 0.90,
        "lossless": 0.15,
    }
    
    max_reduction = quality_factors.get(quality, 0.70)
    estimated_reduction = compressibility * max_reduction * 100
    estimated_size = int(original_size * (1 - estimated_reduction / 100))
    
    result = {
        "original_size": original_size,
        "estimated_size": estimated_size,
        "estimated_reduction": estimated_reduction,
        "preset": quality,
        "compressibility": compressibility,
        "recommendation": analysis.get("recommendation", "smart"),
        "total_images": analysis.get("total_images", 0),
        "image_bytes": analysis.get("total_image_bytes", 0),
        "gs_available": analysis.get("gs_available", False),
    }
    
    return result


# ============================================================
# Feature 1: SSIM Perceptual Quality Metric
# ============================================================

def compute_ssim(original_path: str, compressed_path: str, page: int = 0, dpi: int = 72) -> Dict[str, Any]:
    """Compute SSIM (Structural Similarity Index) between original and compressed PDF.
    
    SSIM measures perceptual quality, not just pixel difference.
    Range: 0.0 (completely different) to 1.0 (identical).
    - > 0.98: Visually perfect (human can't distinguish)
    - > 0.95: Excellent (minor differences visible only at zoom)
    - > 0.90: Good (acceptable for most documents)
    - > 0.80: Fair (visible artifacts)
    - < 0.80: Poor (significant quality loss)
    
    Uses simplified SSIM without scipy dependency.
    
    Args:
        original_path: Path to original PDF
        compressed_path: Path to compressed PDF
        page: Page number to compare (0-indexed)
        dpi: Render DPI for comparison (72 = fast, 150 = accurate)
    
    Returns:
        Dict with ssim, quality_label, avg_pixel_diff, black_percent
    """
    fitz = get_fitz()
    if not fitz or not HAS_PIL:
        return {"error": "PyMuPDF or Pillow not available", "ssim": 0.0}
    
    try:
        doc_orig = fitz.open(original_path)
        doc_comp = fitz.open(compressed_path)
        
        if page >= doc_orig.page_count or page >= doc_comp.page_count:
            return {"error": f"Page {page} out of range", "ssim": 0.0}
        
        # Render pages at specified DPI
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pix_orig = doc_orig[page].get_pixmap(matrix=mat)
        pix_comp = doc_comp[page].get_pixmap(matrix=mat)
        
        doc_orig.close()
        doc_comp.close()
        
        # Convert to PIL for analysis
        img_orig = Image.frombytes("RGB", [pix_orig.width, pix_orig.height], pix_orig.samples)
        img_comp = Image.frombytes("RGB", [pix_comp.width, pix_comp.height], pix_comp.samples)
        
        # Ensure same size
        if img_orig.size != img_comp.size:
            img_comp = img_comp.resize(img_orig.size, Image.LANCZOS)
        
        # Convert to grayscale for SSIM (standard practice)
        gray_orig = img_orig.convert("L")
        gray_comp = img_comp.convert("L")
        
        # Simplified SSIM computation (no scipy needed)
        # SSIM = (2*μx*μy + C1)(2*σxy + C2) / (μx² + μy² + C1)(σx² + σy² + C2)
        import array
        
        width, height = gray_orig.size
        pixels_orig = list(gray_orig.getdata())
        pixels_comp = list(gray_comp.getdata())
        n = len(pixels_orig)
        
        if n == 0:
            return {"error": "Empty image", "ssim": 0.0}
        
        # Block-based SSIM (8x8 blocks, like JPEG)
        block_size = 8
        C1 = (0.01 * 255) ** 2  # Stabilization constants
        C2 = (0.03 * 255) ** 2
        
        ssim_sum = 0.0
        block_count = 0
        total_diff = 0
        
        for by in range(0, height - block_size + 1, block_size):
            for bx in range(0, width - block_size + 1, block_size):
                # Extract block
                block_o = []
                block_c = []
                for y in range(by, by + block_size):
                    for x in range(bx, bx + block_size):
                        idx = y * width + x
                        block_o.append(pixels_orig[idx])
                        block_c.append(pixels_comp[idx])
                
                bs = len(block_o)
                
                # Means
                mu_o = sum(block_o) / bs
                mu_c = sum(block_c) / bs
                
                # Variances and covariance
                var_o = sum((p - mu_o) ** 2 for p in block_o) / bs
                var_c = sum((p - mu_c) ** 2 for p in block_c) / bs
                cov = sum((block_o[i] - mu_o) * (block_c[i] - mu_c) for i in range(bs)) / bs
                
                # SSIM for this block
                numerator = (2 * mu_o * mu_c + C1) * (2 * cov + C2)
                denominator = (mu_o ** 2 + mu_c ** 2 + C1) * (var_o + var_c + C2)
                
                ssim_sum += numerator / denominator if denominator > 0 else 1.0
                block_count += 1
        
        ssim_value = ssim_sum / block_count if block_count > 0 else 0.0
        
        # Also compute simple pixel diff
        for i in range(n):
            total_diff += abs(pixels_orig[i] - pixels_comp[i])
        avg_diff = total_diff / n
        
        # Black percent check
        black_pixels = sum(1 for p in pixels_comp if p < 10)
        black_pct = black_pixels / n * 100
        
        # Quality label
        if ssim_value >= 0.98:
            quality_label = "perfect"
        elif ssim_value >= 0.95:
            quality_label = "excellent"
        elif ssim_value >= 0.90:
            quality_label = "good"
        elif ssim_value >= 0.80:
            quality_label = "fair"
        else:
            quality_label = "poor"
        
        return {
            "ssim": round(ssim_value, 4),
            "quality_label": quality_label,
            "avg_pixel_diff": round(avg_diff, 2),
            "black_percent": round(black_pct, 1),
            "page": page,
            "render_dpi": dpi,
        }
        
    except Exception as e:
        logger.error(f"SSIM computation failed: {e}")
        return {"error": str(e), "ssim": 0.0}


# ============================================================
# Feature 2: Ghostscript-Integrated Compression
# ============================================================

def compress_pdf_hybrid(
    input_path: str,
    output_path: str,
    quality: str = "medium",
    cancel_check=None,
    progress_callback=None,
) -> Tuple[bool, float, Dict[str, Any]]:
    """Compress PDF using hybrid Ghostscript + PyMuPDF pipeline.
    
    Pipeline:
      1. Try Ghostscript hybrid (GS lossy images → PyMuPDF lossless structure)
      2. If GS not available or fails → fallback to compress_pdf_smart()
      3. Compare results, keep the smaller file
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        quality: "extreme"/"low"/"medium"/"high"/"lossless"
        cancel_check: Optional callable returning True to cancel
        progress_callback: Optional callable(percent, message)
    
    Returns:
        Tuple of (success, reduction_percent, stats_dict)
    """
    if not os.path.exists(input_path):
        return False, 0.0, {"error": "File not found"}
    
    original_size = os.path.getsize(input_path)
    if original_size == 0:
        return False, 0.0, {"error": "Empty file"}
    
    # Quality → DPI mapping for Ghostscript
    dpi_map = {
        "extreme": 72,
        "low": 96,
        "medium": 150,
        "high": 200,
        "lossless": 300,
    }
    target_dpi = dpi_map.get(quality, 150)
    
    stats = {
        "pipeline": "unknown",
        "original_size": original_size,
        "gs_available": False,
        "gs_tried": False,
        "gs_success": False,
    }
    
    # Check if Ghostscript is available
    has_gs, hybrid_fn = _get_gs_support()
    stats["gs_available"] = has_gs
    
    if has_gs and hybrid_fn:
        stats["gs_tried"] = True
        
        if progress_callback:
            progress_callback(10, "Ghostscript hybrid compression...")
        
        logger.info(f"Hybrid compress: GS+PyMuPDF (quality={quality}, DPI={target_dpi})")
        
        # Create temp for GS output
        import tempfile
        fd, temp_gs = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        try:
            gs_ok, gs_reduction, gs_pipeline = hybrid_fn(
                input_path, temp_gs, dpi=target_dpi
            )
            
            if gs_ok and gs_reduction > 0:
                stats["gs_success"] = True
                stats["gs_reduction"] = gs_reduction
                
                if progress_callback:
                    progress_callback(50, "Comparing with smart compression...")
                
                # Also try smart compression for comparison
                fd2, temp_smart = tempfile.mkstemp(suffix=".pdf")
                os.close(fd2)
                
                try:
                    smart_ok, smart_red, smart_stats = compress_pdf_smart(
                        input_path, temp_smart, quality=quality
                    )
                    
                    gs_size = os.path.getsize(temp_gs)
                    smart_size = os.path.getsize(temp_smart) if smart_ok else original_size
                    
                    # Pick the smaller result
                    if gs_size <= smart_size:
                        shutil.copy2(temp_gs, output_path)
                        stats["pipeline"] = "ghostscript+pymupdf"
                        stats["chosen"] = "ghostscript"
                        stats["gs_size"] = gs_size
                        stats["smart_size"] = smart_size
                        final_size = gs_size
                    else:
                        shutil.copy2(temp_smart, output_path)
                        stats["pipeline"] = smart_stats.get("pipeline", "pymupdf_smart")
                        stats["chosen"] = "smart"
                        stats["gs_size"] = gs_size
                        stats["smart_size"] = smart_size
                        stats.update(smart_stats)
                        final_size = smart_size
                        
                finally:
                    if os.path.exists(temp_smart):
                        os.remove(temp_smart)
                
                reduction = ((original_size - final_size) / original_size) * 100
                stats["reduction_percent"] = reduction
                stats["final_size"] = final_size
                
                if progress_callback:
                    progress_callback(100, f"Done: {reduction:.1f}% reduced ({stats['chosen']})")
                
                logger.info(f"Hybrid result: GS={gs_size//1024}KB, Smart={smart_size//1024}KB → chose {stats['chosen']}")
                return True, reduction, stats
            else:
                logger.info("GS hybrid didn't help, falling back to smart compression")
        finally:
            if os.path.exists(temp_gs):
                os.remove(temp_gs)
    
    # Fallback: Smart compression only
    if progress_callback:
        progress_callback(30, "Smart compression (no Ghostscript)...")
    
    stats["pipeline"] = "smart_fallback"
    ok, reduction, smart_stats = compress_pdf_smart(
        input_path, output_path, quality=quality,
        progress_callback=progress_callback,
    )
    stats.update(smart_stats)
    return ok, reduction, stats


# ============================================================
# Feature 3: Target Size Mode (Binary Search)
# ============================================================

def compress_to_target_size(
    input_path: str,
    output_path: str,
    target_kb: int,
    min_quality: int = 10,
    max_quality: int = 95,
    max_iterations: int = 7,
    cancel_check=None,
    progress_callback=None,
) -> Tuple[bool, float, Dict[str, Any]]:
    """Compress PDF to a target file size using binary search for optimal JPEG quality.
    
    Finds the HIGHEST quality setting that results in file size ≤ target_kb.
    This gives the best visual quality for the given size constraint.
    
    Algorithm:
      1. Binary search on JPEG quality (10-95)
      2. Each iteration compresses, checks size, adjusts quality
      3. After convergence, pick highest quality under target
      4. If target not achievable even at min quality → return best effort with warning
    
    Args:
        input_path: Path to input PDF
        output_path: Path to output PDF
        target_kb: Target file size in KB
        min_quality: Minimum JPEG quality to try (default 10)
        max_quality: Maximum JPEG quality to try (default 95)
        max_iterations: Max binary search iterations (default 7 = ~1% precision)
        cancel_check: Optional callable returning True to cancel
        progress_callback: Optional callable(percent, message)
    
    Returns:
        Tuple of (success, reduction_percent, stats_dict)
    """
    if not os.path.exists(input_path):
        return False, 0.0, {"error": "File not found"}
    
    # Input validation
    if target_kb < 10:
        return False, 0.0, {"error": f"Target too small ({target_kb}KB). Minimum is 10KB."}
    
    original_size = os.path.getsize(input_path)
    original_kb = original_size / 1024
    target_bytes = target_kb * 1024
    
    if original_size <= target_bytes:
        # Already under target
        shutil.copy(input_path, output_path)
        return True, 0.0, {
            "pipeline": "target_size",
            "note": "Already under target size",
            "original_kb": round(original_kb, 1),
            "target_kb": target_kb,
            "final_kb": round(original_kb, 1),
            "quality_used": 95,
        }
    
    import tempfile
    
    stats = {
        "pipeline": "target_size",
        "original_kb": round(original_kb, 1),
        "target_kb": target_kb,
        "iterations": 0,
        "search_log": [],
    }
    
    lo = min_quality
    hi = max_quality
    best_quality = None
    best_size = None
    best_temp = None
    
    logger.info(f"Target Size Mode: {original_kb:.1f}KB → ≤{target_kb}KB (binary search)")
    
    for iteration in range(max_iterations):
        if cancel_check and cancel_check():
            return False, 0.0, {"error": "Cancelled", "cancelled": True}
        
        quality = (lo + hi) // 2
        stats["iterations"] += 1
        
        if progress_callback:
            pct = int((iteration + 1) / max_iterations * 80)
            progress_callback(pct, f"Testing quality={quality}% (iteration {iteration+1}/{max_iterations})")
        
        # Create temp output
        fd, temp_path = tempfile.mkstemp(suffix=".pdf")
        os.close(fd)
        
        try:
            # Map quality integer to DPI+JPEG settings
            if quality >= 70:
                preset_dpi = 150
            elif quality >= 40:
                preset_dpi = 96
            else:
                preset_dpi = 72
            
            # Compress with these settings
            ok, _, _ = compress_pdf_advanced(
                input_path, temp_path, quality="custom",
                target_dpi=preset_dpi, jpeg_quality=quality,
                cancel_check=cancel_check,
            )
            
            if not ok or not os.path.exists(temp_path):
                # Compression failed at this quality, try lower
                hi = quality - 1
                stats["search_log"].append({"quality": quality, "result": "failed"})
                continue
            
            result_size = os.path.getsize(temp_path)
            result_kb = result_size / 1024
            
            stats["search_log"].append({
                "quality": quality,
                "size_kb": round(result_kb, 1),
                "under_target": result_size <= target_bytes,
            })
            
            logger.info(f"  Binary search [{iteration+1}]: quality={quality}% → {result_kb:.1f}KB {'✅' if result_size <= target_bytes else '❌'}")
            
            if result_size <= target_bytes:
                # Under target — save as best, try higher quality
                if best_temp and os.path.exists(best_temp):
                    os.remove(best_temp)
                best_quality = quality
                best_size = result_size
                best_temp = temp_path
                lo = quality + 1
            else:
                # Over target — try lower quality
                os.remove(temp_path)
                hi = quality - 1
                
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            hi = quality - 1
            stats["search_log"].append({"quality": quality, "result": f"error: {e}"})
        
        if lo > hi:
            break
    
    # Use best result
    if best_temp and os.path.exists(best_temp):
        shutil.copy2(best_temp, output_path)
        os.remove(best_temp)
        
        final_size = os.path.getsize(output_path)
        reduction = ((original_size - final_size) / original_size) * 100
        
        stats["quality_used"] = best_quality
        stats["final_kb"] = round(final_size / 1024, 1)
        stats["reduction_percent"] = round(reduction, 1)
        stats["target_achieved"] = True
        
        if progress_callback:
            progress_callback(100, f"Target achieved: {final_size//1024}KB ≤ {target_kb}KB (quality={best_quality}%)")
        
        logger.info(f"✅ Target Size reached: {original_kb:.1f}KB → {final_size//1024}KB (quality={best_quality}%, {stats['iterations']} iterations)")
        return True, reduction, stats
    else:
        # Could not reach target even at min quality
        # Return the smallest compression we can do
        logger.warning(f"Could not reach target {target_kb}KB even at quality={min_quality}%")
        
        # Do one final attempt at minimum quality
        ok, reduction, final_stats = compress_pdf_advanced(
            input_path, output_path, quality="custom",
            target_dpi=72, jpeg_quality=min_quality,
            cancel_check=cancel_check,
        )
        
        final_size = os.path.getsize(output_path) if os.path.exists(output_path) else original_size
        stats["quality_used"] = min_quality
        stats["final_kb"] = round(final_size / 1024, 1)
        stats["reduction_percent"] = round(reduction, 1) if ok else 0.0
        stats["target_achieved"] = False
        stats["note"] = f"Target {target_kb}KB not achievable. Best: {final_size//1024}KB at quality={min_quality}%"
        
        if progress_callback:
            progress_callback(100, f"Best effort: {final_size//1024}KB (target {target_kb}KB not achievable)")
        
        return ok, reduction, stats

