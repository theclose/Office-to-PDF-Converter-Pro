"""
TkinterDnD2 + CustomTkinter Integration
Provides wrapper class for combining tkinterdnd2 with customtkinter.
"""

import logging
import customtkinter as ctk

logger = logging.getLogger(__name__)

# Try to import tkinterdnd2
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_TKDND = True
except ImportError:
    HAS_TKDND = False
    logger.warning("tkinterdnd2 not installed - drag drop will be disabled")
    # Create dummy class for fallback
    class TkinterDnD:
        class Tk:
            pass
    DND_FILES = None


class TkDnDWrapper(ctk.CTk, TkinterDnD.Tk):
    """
    Custom wrapper combining CustomTkinter with TkinterDnD2 via multiple inheritance.
    
    WHY MULTIPLE INHERITANCE IS REQUIRED:
    --------------------------------------
    CustomTkinter (ctk.CTk) is a modern wrapper around tkinter.Tk that adds:
    - Dark/light theme support
    - Modern styled widgets
    - Better UI components
    
    However, ctk.CTk does NOT expose drag-and-drop hooks.
    
    TkinterDnD2 (TkinterDnD.Tk) modifies the Tcl/Tk interpreter at a low level to:
    - Register drag-drop event handlers
    - Add <<Drop>> virtual events
    - Provide file path extraction
    
    By using multiple inheritance:
    1. We get CustomTkinter's modern UI and theming system
    2. We inject TkinterDnD's low-level Tcl hooks into the SAME Tk instance
    3. Both frameworks operate on the same underlying Tcl interpreter
    
    CRITICAL IMPLEMENTATION NOTES:
    -------------------------------
    - Order matters! ctk.CTk MUST come first in the inheritance list
    - This ensures CustomTkinter's __init__ runs first to set up the theme system
    - Then TkinterDnD.Tk patches the Tcl interpreter to add DnD support
    - Both modifications are compatible and don't conflict
    
    This is the ONLY way to combine these libraries without rewriting
    CustomTkinter's entire widget system from scratch.
    
    ALTERNATIVE APPROACHES (and why they don't work):
    --------------------------------------------------
    1. Composition: Doesn't work - can't have two separate Tk instances
    2. Monkey-patching: Too fragile and breaks on updates
    3. Forking CustomTkinter: Unmaintainable
    
    Usage:
        class MyApp(TkDnDWrapper):
            def __init__(self):
                super().__init__()
                self.title("My App")
                self._setup_dnd()
    """
    
    def __init__(self, *args, **kwargs):
        """
        Initialize both parent classes.
        
        CRITICAL: We must call BOTH parent __init__ methods explicitly
        because super() with multiple inheritance won't work correctly here.
        
        Order matters:
        1. ctk.CTk creates the Tk instance
        2. TkinterDnD.Tk patches the Tcl interpreter to add DnD support
        3. Reapply CustomTkinter theme (TkinterDnD may override some settings)
        """
        # First initialize CustomTkinter (creates base Tk window)
        ctk.CTk.__init__(self, *args, **kwargs)
        
        # Then initialize TkinterDnD on the SAME Tk instance
        # This call adds tkdnd library path to Tcl and loads the package
        try:
            # Call TkinterDnD.Tk's init logic manually
            # TkinterDnD.Tk.__init__ expects 'self' to be a Tk instance (which it now is)
            TkinterDnD.Tk.__init__(self)
            
            # IMPORTANT: Reapply CustomTkinter appearance mode and theme
            # TkinterDnD initialization may have reset some Tk defaults
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")
            
            # Force update the widget colors
            self.configure(fg_color=("gray95", "gray10"))
            
            logger.info("TkDnD + CustomTkinter wrapper initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize TkinterDnD: {e}")
            raise


def setup_widget_dnd(widget, callback, file_types=None):
    """
    Setup drag-and-drop on a CustomTkinter widget.
    
    This is a helper function for widgets that can't use multiple inheritance.
    
    Args:
        widget: CustomTkinter widget to enable DnD on
        callback: Function(List[str]) called with validated file paths
        file_types: Optional filter (currently not used, accepts all files)
        
    Returns:
        bool: True if DnD was successfully enabled, False otherwise
        
    Example:
        frame = ctk.CTkFrame(root)
        setup_widget_dnd(frame, lambda paths: print(f"Dropped: {paths}"))
    """
    if not HAS_TKDND:
        logger.warning("tkinterdnd2 not available - cannot setup DnD")
        return False
        
    try:
        # Register widget to accept file drops
        widget.drop_target_register(DND_FILES)
        
        # Bind drop event with our callback wrapper
        def handle_drop(event):
            try:
                from office_converter.utils.dnd_helpers import parse_dropped_paths
                
                # Get root window for tk.splitlist
                root = widget.winfo_toplevel()
                
                # Parse paths safely
                file_paths = parse_dropped_paths(root, event.data)
                
                if file_paths:
                    callback(file_paths)
                    logger.info(f"DnD: Processed {len(file_paths)} file(s)")
                else:
                    logger.warning("DnD: No valid files in drop event")
                    
            except Exception as e:
                logger.error(f"DnD handler error: {e}", exc_info=True)
        
        widget.dnd_bind('<<Drop>>', handle_drop)
        
        logger.info(f"DnD enabled on {widget.__class__.__name__}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to setup DnD: {e}", exc_info=True)
        return False
