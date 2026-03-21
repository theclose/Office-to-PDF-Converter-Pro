"""
Ghostscript wrapper for PDF compression.
Provides hybrid pipeline: GS (lossy image compression) + PyMuPDF (lossless structure).

Auto-detects Ghostscript on Windows:
  1. System PATH
  2. Program Files
  3. Local bin/ folder (portable)

Falls back gracefully if GS not found — callers should check HAS_GS flag.
"""

import os
import subprocess
import tempfile
import shutil
import logging
from typing import Tuple, Optional

logger = logging.getLogger("pdf_tools")

# Ghostscript auto-detection
_gs_path: Optional[str] = None
HAS_GS: bool = False


def find_ghostscript() -> Optional[str]:
    """Auto-detect Ghostscript executable on Windows.
    
    Search order:
      1. System PATH (gswin64c, gswin32c, gs)
      2. Program Files installations
      3. Local bin/ folder (portable deployment)
    
    Returns:
        Path to gs executable, or None if not found.
    """
    global _gs_path, HAS_GS
    
    if _gs_path is not None:
        return _gs_path if _gs_path else None
    
    # 1. Check PATH
    for name in ["gswin64c", "gswin32c", "gs"]:
        try:
            result = subprocess.run(
                [name, "--version"],
                capture_output=True, timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
            if result.returncode == 0:
                _gs_path = name
                HAS_GS = True
                version = result.stdout.decode().strip()
                logger.info(f"Ghostscript found in PATH: {name} v{version}")
                return _gs_path
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            continue
    
    # 2. Check Program Files
    search_dirs = []
    for pf in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
        if pf:
            gs_dir = os.path.join(pf, "gs")
            if os.path.isdir(gs_dir):
                search_dirs.append(gs_dir)
    
    for search_dir in search_dirs:
        for root, dirs, files in os.walk(search_dir):
            for fname in files:
                if fname.lower() in ("gswin64c.exe", "gswin32c.exe"):
                    candidate = os.path.join(root, fname)
                    try:
                        result = subprocess.run(
                            [candidate, "--version"],
                            capture_output=True, timeout=5,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                        )
                        if result.returncode == 0:
                            _gs_path = candidate
                            HAS_GS = True
                            logger.info(f"Ghostscript found: {candidate}")
                            return _gs_path
                    except (subprocess.TimeoutExpired, OSError):
                        continue
    
    # 3. Check local bin/ folder
    app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for bin_name in ["gswin64c.exe", "gswin32c.exe"]:
        candidate = os.path.join(app_root, "bin", bin_name)
        if os.path.isfile(candidate):
            _gs_path = candidate
            HAS_GS = True
            logger.info(f"Ghostscript found (portable): {candidate}")
            return _gs_path
    
    _gs_path = ""  # Mark as searched but not found
    HAS_GS = False
    logger.info("Ghostscript not found — will use PyMuPDF-only compression")
    return None


def compress_with_gs(
    input_path: str,
    output_path: str,
    dpi: int = 150,
    color_conversion: bool = True,
    timeout: int = 300,
) -> Tuple[bool, str]:
    """Compress PDF using Ghostscript (Tầng 1: lossy image compression).
    
    Applies:
      - Bicubic downsampling for color/gray images  
      - CMYK → sRGB color space conversion
      - CCITTFax for mono images (B&W scan preservation at 300 DPI)
      - Auto filter selection (JPEG/JPEG2000/Flate per image)
    
    Args:
        input_path: Source PDF file
        output_path: Destination PDF file
        dpi: Target DPI for color/gray images (default 150)
        color_conversion: Convert CMYK to sRGB (default True)
        timeout: Max seconds to wait for GS (default 300)
    
    Returns:
        Tuple of (success, message)
    """
    gs_exe = find_ghostscript()
    if not gs_exe:
        return False, "Ghostscript not found"
    
    if not os.path.exists(input_path):
        return False, f"Input file not found: {input_path}"
    
    # Build GS command with optimal settings
    cmd = [
        gs_exe,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        
        # --- Color image handling (Bicubic = smooth downsampling) ---
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        f"-dColorImageResolution={dpi}",
        "-dAutoFilterColorImages=true",  # Let GS auto-choose JPEG/JPEG2000/Flate
        
        # --- Gray image handling ---
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        f"-dGrayImageResolution={dpi}",
        "-dAutoFilterGrayImages=true",
        
        # --- Mono (B&W) image handling ---
        # Keep at 300 DPI + CCITTFax to preserve text sharpness in scans
        "-dDownsampleMonoImages=true",
        "-dMonoImageDownsampleType=/Subsample",
        "-dMonoImageResolution=300",
        "-dMonoImageFilter=/CCITTFaxEncode",
        
        # --- Output ---
        f"-sOutputFile={output_path}",
        input_path,
    ]
    
    # Add color conversion if requested
    if color_conversion:
        cmd.insert(-2, "-sColorConversionStrategy=sRGB")
        cmd.insert(-2, "-dProcessColorModel=/DeviceRGB")
    
    logger.info(f"GS compress: DPI={dpi}, color_convert={color_conversion}")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            logger.warning(f"GS returned code {result.returncode}: {stderr[:200]}")
            # GS may still produce output even with non-zero return code
            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                return False, f"GS failed (code {result.returncode}): {stderr[:100]}"
        
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            return True, "Ghostscript compression complete"
        else:
            return False, "GS produced no output"
            
    except subprocess.TimeoutExpired:
        logger.error(f"GS timed out after {timeout}s")
        # Clean up partial output
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass
        return False, f"Ghostscript timed out ({timeout}s)"
    except FileNotFoundError:
        logger.error("GS executable not found at runtime")
        return False, "Ghostscript executable not found"
    except Exception as e:
        logger.error(f"GS error: {e}")
        return False, str(e)


def hybrid_compress(
    input_path: str,
    output_path: str,
    dpi: int = 150,
    timeout: int = 300,
) -> Tuple[bool, float, str]:
    """Hybrid Pipeline: Ghostscript → PyMuPDF → Smart Fallback.
    
    Tầng 1: GS lossy image compression (Bicubic + sRGB)
    Tầng 2: PyMuPDF lossless structure optimization (scrub + subset + garbage=4)
    Tầng 3: Smart fallback — if result larger than original, use PyMuPDF-only
    
    Args:
        input_path: Source PDF
        output_path: Destination PDF
        dpi: Target DPI for images
        timeout: Max seconds for GS subprocess
        
    Returns:
        Tuple of (success, reduction_percent, pipeline_used)
    """
    from .common import get_fitz
    
    fitz = get_fitz()
    if not fitz:
        return False, 0.0, "error: PyMuPDF not available"
    
    original_size = os.path.getsize(input_path)
    if original_size == 0:
        return False, 0.0, "error: empty file"
    
    gs_exe = find_ghostscript()
    
    if not gs_exe:
        # No GS → PyMuPDF-only path
        return _pymupdf_only_compress(fitz, input_path, output_path, original_size)
    
    # Create temp files for pipeline stages
    fd1, temp_gs = tempfile.mkstemp(suffix=".pdf")
    os.close(fd1)
    fd2, temp_final = tempfile.mkstemp(suffix=".pdf")
    os.close(fd2)
    
    try:
        # === TẦNG 1: Ghostscript (lossy image compression) ===
        logger.info("Hybrid Pipeline — Tầng 1: Ghostscript image compression")
        gs_ok, gs_msg = compress_with_gs(input_path, temp_gs, dpi=dpi, timeout=timeout)
        
        if not gs_ok:
            logger.warning(f"GS failed ({gs_msg}), falling back to PyMuPDF-only")
            return _pymupdf_only_compress(fitz, input_path, output_path, original_size)
        
        # === TẦNG 2: PyMuPDF (lossless structure optimization) ===
        logger.info("Hybrid Pipeline — Tầng 2: PyMuPDF structure optimization")
        try:
            doc = fitz.open(temp_gs)
            
            # Scrub metadata
            try:
                doc.scrub(
                    attached_files=True, clean_pages=True, embedded_files=True,
                    hidden_text=True, javascript=True, metadata=True,
                    redact_images=0, redactions=True, remove_links=False,
                    reset_fields=True, reset_responses=True,
                    thumbnails=True, xml_metadata=True,
                )
            except Exception:
                pass
            
            # Font subsetting
            try:
                doc.subset_fonts()
            except Exception:
                pass
            
            # Save with max garbage collection
            doc.save(
                temp_final,
                garbage=4,        # Max: deduplicate + remove orphans
                deflate=True,     # Zlib compress streams
                clean=True,       # Fix syntax errors
                pretty=False,     # No pretty-print (smaller)
                no_new_id=True,
            )
            doc.close()
        except Exception as e:
            logger.warning(f"PyMuPDF stage failed: {e}")
            # If PyMuPDF fails on GS output, try PyMuPDF on original
            return _pymupdf_only_compress(fitz, input_path, output_path, original_size)
        
        # === TẦNG 3: Smart Fallback ===
        final_size = os.path.getsize(temp_final)
        
        if final_size < original_size:
            shutil.copy2(temp_final, output_path)
            reduction = ((original_size - final_size) / original_size) * 100
            logger.info(
                f"Hybrid Pipeline success: {original_size//1024}KB → {final_size//1024}KB "
                f"({reduction:.1f}% reduced)"
            )
            return True, reduction, "ghostscript+pymupdf"
        else:
            # GS made it larger → fallback to PyMuPDF-only on original
            logger.info("Hybrid result larger than original — falling back to PyMuPDF-only")
            return _pymupdf_only_compress(fitz, input_path, output_path, original_size)
            
    finally:
        # Clean up temp files
        for tmp in [temp_gs, temp_final]:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


def _pymupdf_only_compress(fitz, input_path: str, output_path: str, original_size: int) -> Tuple[bool, float, str]:
    """PyMuPDF-only compression (lossless structure optimization)."""
    try:
        doc = fitz.open(input_path)
        
        try:
            doc.scrub(
                attached_files=True, clean_pages=True, embedded_files=True,
                hidden_text=True, javascript=True, metadata=True,
                redact_images=0, redactions=True, remove_links=False,
                reset_fields=True, reset_responses=True,
                thumbnails=True, xml_metadata=True,
            )
        except Exception:
            pass
        
        try:
            doc.subset_fonts()
        except Exception:
            pass
        
        doc.save(
            output_path,
            garbage=4, deflate=True, clean=True,
            pretty=False, no_new_id=True,
        )
        doc.close()
        
        new_size = os.path.getsize(output_path)
        if new_size >= original_size:
            shutil.copy2(input_path, output_path)
            return True, 0.0, "pymupdf_only (no reduction)"
        
        reduction = ((original_size - new_size) / original_size) * 100
        return True, reduction, "pymupdf_only"
        
    except Exception as e:
        logger.error(f"PyMuPDF-only compress failed: {e}")
        return False, 0.0, f"error: {e}"
