"""
Office Converter Reactor UI - Entry Point
=========================================
Launches the modern, event-driven, autonomous grid UI.

Usage:
    python run_reactor.py
"""
import sys
import os

# Ensure package is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    
# Add parent dir for office_converter package resolution
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

if __name__ == "__main__":
    from office_converter.grid.reactor.reactor_app import ReactorApp
    # Note: shim is in grid/shim.py, not grid/reactor/shim.py
    # from office_converter.grid.shim import install_shim_layer

    print("🚀 Initializing Reactor Grid...")
    
    # 1. Install shim to neutralize legacy modules (if needed)
    # install_shim_layer() 
    
    # 2. Launch App
    app = ReactorApp()
    print("✅ Reactor UI running.")
    app.mainloop()
