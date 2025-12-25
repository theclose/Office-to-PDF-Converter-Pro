
"""Office to PDF Converter Pro - Entry Point"""
import sys
import os

# Add parent directory to path (so office_converter package can be imported)
project_root = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(project_root)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == "__main__":
    from office_converter.ui.main_window_pro import ConverterProApp
    app = ConverterProApp()
    app.mainloop()
