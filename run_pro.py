
"""
Office to PDF Converter Pro - Entry Point (LEGACY)

⚠️ DEPRECATED: This entry point uses the legacy monolithic UI.
   Please use run_reactor.py for the modern event-driven UI:
   
   python run_reactor.py
"""
import sys
import os
import ctypes
import logging
import threading
import traceback
import warnings

# ============================================================================
# U1: DPI Awareness — MUST be set BEFORE any tkinter/GUI import
# Without this, app is blurry on Windows Scale >100% (30%+ of users)
# ============================================================================
if sys.platform == 'win32':
    try:
        # Per-Monitor DPI Awareness V2 (Windows 10 1703+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        try:
            # Fallback: System DPI Aware
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

# Add parent directory to path (so office_converter package can be imported)
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


# ============================================================================
# C1 + C2: Global Exception Hooks — prevent silent crashes
# ============================================================================

def _setup_exception_hooks():
    """Install global exception hooks to log uncaught exceptions.
    
    Without these, uncaught exceptions on main thread crash the app
    silently (no log), and worker thread exceptions are swallowed
    entirely when console=False (packaged EXE).
    """
    crash_logger = logging.getLogger("office_converter.crash")

    def _main_thread_hook(exc_type, exc_value, exc_tb):
        """sys.excepthook — catches main thread uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        crash_logger.critical(
            "UNCAUGHT EXCEPTION (main thread):\n"
            + "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        )
        # Flush all handlers so the crash log is persisted
        for handler in logging.root.handlers + crash_logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass

    def _worker_thread_hook(args):
        """threading.excepthook — catches worker thread uncaught exceptions."""
        crash_logger.critical(
            f"UNCAUGHT EXCEPTION (thread: {args.thread.name if args.thread else 'unknown'}):\n"
            + "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )
        for handler in logging.root.handlers + crash_logger.handlers:
            try:
                handler.flush()
            except Exception:
                pass

    sys.excepthook = _main_thread_hook
    threading.excepthook = _worker_thread_hook

_setup_exception_hooks()

if __name__ == "__main__":
    # P2: Show deprecation warning
    warnings.warn(
        "\n\n"
        "⚠️  DEPRECATION WARNING ⚠️\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "run_pro.py uses the legacy monolithic UI.\n"
        "Please switch to the modern Reactor UI:\n\n"
        "    python run_reactor.py\n\n"
        "The legacy UI will be removed in a future version.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n",
        DeprecationWarning,
        stacklevel=2
    )
    
    from office_converter.ui.main_window_pro import ConverterProApp
    app = ConverterProApp()
    app.mainloop()
