"""
PDF Compression Module.
Professional implementation based on PyMuPDF best practices.
"""

import os
import io
import shutil
from typing import Tuple, Dict, Any

from .common import get_fitz, HAS_PYMUPDF, HAS_PIL, logger

try:
    from PIL import Image
except ImportError:
    pass

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
    if not fitz or not HAS_PYMUPDF:
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
    progress_callback: callable = None,  # NEW: progress_callback(current, total, percent)
    cancel_check: callable = None,       # NEW: cancel_check() -> bool
) -> Tuple[bool, float, Dict[str, Any]]:
    fitz = get_fitz()
    if not fitz or not HAS_PYMUPDF:
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
        "fonts_subsetted": False,
        "metadata_removed": False,
    }
    
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
            logger.info(f"Phase 3: Image compression (DPI={target_dpi}, Quality={jpeg_quality}%)")
            
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
                    # B6: Skip tiny images (raised from 5KB to 10KB)
                    if original_img_size < 10000 or not HAS_PIL:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        continue
                    pil_img = Image.open(io.BytesIO(image_bytes))
                    if grayscale:
                        pil_img = pil_img.convert("L")
                    elif pil_img.mode not in ("RGB", "L"):
                        pil_img = pil_img.convert("RGB")
                    # B6: Skip resize if image already fits within target dimensions
                    if pil_img.width > max_dim or pil_img.height > max_dim:
                        ratio = min(max_dim / pil_img.width, max_dim / pil_img.height)
                        pil_img = pil_img.resize((int(pil_img.width * ratio), int(pil_img.height * ratio)), Image.LANCZOS)
                    elif pil_img.width <= 100 and pil_img.height <= 100:
                        # B6: Skip very small images entirely (icons, bullets)
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                        pil_img = None
                        continue
                    buffer = io.BytesIO()
                    pil_img.save(buffer, "JPEG", quality=jpeg_quality, optimize=True)
                    compressed = buffer.getvalue()
                    if len(compressed) < original_img_size * 0.9:
                        xref_data[xref] = compressed
                        stats["images_optimized"] += 1
                    else:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                    pil_img = None
                    buffer = None
                except Exception as e:
                    logger.warning(f"Could not process image {xref}: {e}")
                    xref_data[xref] = None
                    stats["images_skipped"] += 1
            
            current_progress = 0
            total_tasks = len(image_tasks)
            for page_num, xref, rect in image_tasks:
                current_progress += 1
                compressed = xref_data.get(xref)
                if compressed is None:
                    continue
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
                        doc.xref_set_key(xref, "Width", "1")
                        doc.xref_set_key(xref, "Height", "1")
                        doc.update_stream(xref, b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9telecast:telecast\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\xff\xd9')
                        stats["images_optimized"] += 1
                    except:
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
            import shutil
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
    fitz = get_fitz()
    if not fitz or not HAS_PYMUPDF or not os.path.exists(input_path):
        return {"error": "File not found or PyMuPDF not available"}
    
    try:
        doc = fitz.open(input_path)
        analysis = {
            "total_pages": doc.page_count,
            "text_pages": [],
            "image_pages": [],
            "mixed_pages": [],
            "total_images": 0,
            "total_image_bytes": 0,
            "has_text": False
        }
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            images = page.get_images(full=True)
            image_count = len(images)
            text = page.get_text("text").strip()
            has_text = len(text) > 50
            
            for img in images:
                xref = img[0]
                try:
                    base_img = doc.extract_image(xref)
                    analysis["total_image_bytes"] += len(base_img.get("image", b""))
                except:
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
        
        doc.close()
        
        if len(analysis["image_pages"]) == analysis["total_pages"]:
            analysis["recommendation"] = "rasterize"
        elif len(analysis["text_pages"]) == analysis["total_pages"]:
            analysis["recommendation"] = "lossless"
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
    if not fitz or not HAS_PYMUPDF or not HAS_PIL:
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
        "images_compressed": 0,
        "images_skipped": 0,
        "text_preserved": True,
        "bytes_saved_images": 0,
        "method": "smart_selective"
    }
    
    try:
        doc = fitz.open(input_path)
        logger.info(f"Smart compression: {doc.page_count} pages, quality={quality}")
        
        logger.info("Phase 1: Metadata cleanup...")
        try:
            doc.scrub(redact_images=0, garbage=4)
        except:
            pass
        
        logger.info("Phase 2: Font subsetting...")
        try:
            doc.subset_fonts()
        except:
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
                    if pil_img.mode in ("RGBA", "P", "LA"):
                        pil_img = pil_img.convert("RGB")
                    elif pil_img.mode == "CMYK":
                        pil_img = pil_img.convert("RGB")
                    elif pil_img.mode not in ("RGB", "L"):
                        pil_img = pil_img.convert("RGB")
                    
                    max_dim = settings["max_dim"]
                    if pil_img.width > max_dim or pil_img.height > max_dim:
                        ratio = min(max_dim / pil_img.width, max_dim / pil_img.height)
                        new_size = (int(pil_img.width * ratio), int(pil_img.height * ratio))
                        pil_img = pil_img.resize(new_size, Image.LANCZOS)
                    
                    buffer = io.BytesIO()
                    pil_img.save(buffer, "JPEG", quality=settings["jpeg_quality"], optimize=True)
                    compressed_bytes = buffer.getvalue()
                    
                    if len(compressed_bytes) < original_img_size * 0.9:
                        xref_data[xref] = (compressed_bytes, original_img_size)
                        stats["images_compressed"] += 1
                        stats["bytes_saved_images"] += original_img_size - len(compressed_bytes)
                    else:
                        xref_data[xref] = None
                        stats["images_skipped"] += 1
                    
                    pil_img = None
                    buffer = None
                        
                except Exception as e:
                    logger.warning(f"Could not process image {xref}: {e}")
                    xref_data[xref] = None
                    stats["images_skipped"] += 1
        
        for page_num, xref, rect in image_tasks:
            data = xref_data.get(xref)
            if data is None:
                continue
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
            import shutil
            shutil.copy(input_path, output_path)
            logger.info("Compression made file larger, keeping original")
            return True, 0.0, stats
        
        reduction = ((original_size - new_size) / original_size) * 100
        stats["reduction_percent"] = reduction
        stats["saved_bytes"] = original_size - new_size
        
        logger.info(f"✅ Smart Success: {original_size//1024}KB → {new_size//1024}KB ({reduction:.1f}% smaller)")
        
        return True, reduction, stats
        
    except Exception as e:
        logger.error(f"Smart compression failed: {e}")
        return False, 0.0, {"error": str(e)}


def estimate_compression(input_path: str, quality: str = "medium") -> Dict[str, Any]:
    if not os.path.exists(input_path):
        return {"error": "File not found"}
    
    original_size = os.path.getsize(input_path)
    estimates = {
        "low": 0.15,
        "medium": 0.30,
        "high": 0.50,
        "extreme": 0.08,
        "lossless": 0.85,
    }
    
    factor = estimates.get(quality, 0.30)
    estimated_size = int(original_size * factor)
    estimated_reduction = (1 - factor) * 100
    
    return {
        "original_size": original_size,
        "estimated_size": estimated_size,
        "estimated_reduction": estimated_reduction,
        "preset": quality,
    }
