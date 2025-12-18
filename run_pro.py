#!/usr/bin/env python
"""Office to PDF Converter Pro - Entry Point"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if __name__ == "__main__":
    from office_converter.ui.main_window_pro import ConverterProApp
    app = ConverterProApp()
    app.mainloop()
