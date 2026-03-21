"""
PDF Watermark module.
"""

import os
from typing import Tuple

from .common import get_fitz, logger

def add_watermark(
    input_path: str,
    output_path: str,
    text: str,
    opacity: float = 0.3,
    font_size: int = 60,
    color: Tuple[float, float, float] = (0.7, 0.7, 0.7),
    rotation: int = 0  # Only 0, 90, 180, 270 are valid
) -> bool:
    """Add text watermark to all pages of a PDF.
    
    Note: opacity parameter is accepted for API compatibility but
    fitz.insert_text does not support transparency. For true opacity,
    use overlay with a separate transparent PDF.
    """
    fitz = get_fitz()
    if not fitz:
        return False

    if not os.path.exists(input_path):
        return False

    # Validate rotation
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
