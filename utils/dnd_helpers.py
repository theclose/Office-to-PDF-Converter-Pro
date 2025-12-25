"""
Drag & Drop Helper Utilities
Provides robust path parsing for TkinterDnD2 events with full Unicode support.
"""

import os
import logging
from typing import List

logger = logging.getLogger(__name__)


def parse_dropped_paths(tk_root, event_data: str) -> List[str]:
    """
    Parse dropped file paths from TkinterDnD2 event data with production-grade handling.
    
    This function handles the complex path parsing from Tcl/Tk's drag-and-drop
    event data, which wraps paths with spaces in curly braces.
    
    CRITICAL IMPLEMENTATION NOTES:
    ------------------------------
    - MUST use tk.splitlist() to parse Tcl list format correctly
    - This handles curly braces, spaces, and Unicode characters properly
    - DO NOT use manual string parsing (replace, split, regex) - it will fail on edge cases
    
    Args:
        tk_root: The Tk root instance (needed for tk.splitlist)
        event_data: Raw string from drop event
                   Examples:
                   - Single file with spaces: {C:/My Files/Tài liệu.pdf}
                   - Multiple files: {C:/File 1.txt} C:/File2.txt
                   - Vietnamese: {C:/Nguyễn Văn A/Đánh giá.xlsx}
    
    Returns:
        List of normalized, validated file paths that exist on filesystem
        
    Examples:
        >>> parse_dropped_paths(root, "{C:/My Files/Tài liệu.pdf}")
        ["C:\\My Files\\Tài liệu.pdf"]
        
        >>> parse_dropped_paths(root, "{C:/File 1.txt} C:/File2.txt")
        ["C:\\File 1.txt", "C:\\File2.txt"]
    """
    valid_paths = []
    
    try:
        # CRITICAL: Use tk.splitlist() - the ONLY correct way to parse Tcl lists
        # This is the native Tcl parser that handles all edge cases correctly
        raw_paths = tk_root.tk.splitlist(event_data)
        
        for raw_path in raw_paths:
            # Clean up whitespace
            cleaned_path = raw_path.strip()
            
            if not cleaned_path:
                continue
            
            # Normalize path separators (/ → \ on Windows)
            normalized_path = os.path.normpath(cleaned_path)
            
            # Verify path exists before adding to result
            if os.path.exists(normalized_path):
                valid_paths.append(normalized_path)
                logger.debug(f"Valid dropped path: {normalized_path}")
            else:
                logger.warning(f"Dropped path does not exist: {normalized_path}")
                
    except Exception as e:
        logger.error(f"Error parsing dropped paths: {e}", exc_info=True)
        
    return valid_paths
