
"""
Office to PDF Converter Pro - Entry Point (LEGACY)

⚠️ DEPRECATED: This entry point uses the legacy monolithic UI.
   Please use run_reactor.py for the modern event-driven UI:
   
   python run_reactor.py
"""
import sys
import os
import warnings

# Add parent directory to path (so office_converter package can be imported)
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

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
