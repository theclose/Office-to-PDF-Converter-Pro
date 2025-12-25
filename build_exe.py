"""
Office to PDF Converter Pro - Build Script
Version 4.0.7 - Optimized Build

Usage:
    python build_exe.py          # Build .exe
    python build_exe.py --clean  # Clean build files
"""

import sys
import shutil
import subprocess
from pathlib import Path

# Project info
APP_NAME = "OfficeToPDF_Pro"
VERSION = "4.0.8"
MAIN_SCRIPT = "run_pro.py"

# Directories
PROJECT_ROOT = Path(__file__).parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
ASSETS_DIR = PROJECT_ROOT / "assets"


def clean():
    """Clean build artifacts."""
    print("🧹 Cleaning build artifacts...")
    
    for folder in [DIST_DIR, BUILD_DIR]:
        if folder.exists():
            shutil.rmtree(folder)
            print(f"  Removed: {folder}")
    
    # Remove spec file
    spec_file = PROJECT_ROOT / f"{APP_NAME}.spec"
    if spec_file.exists():
        spec_file.unlink()
        print(f"  Removed: {spec_file}")
    
    print("✅ Clean complete!")


def create_version_info():
    """Create version info file for Windows."""
    version_parts = VERSION.split(".")
    major = version_parts[0] if len(version_parts) > 0 else "1"
    minor = version_parts[1] if len(version_parts) > 1 else "0"
    patch = version_parts[2] if len(version_parts) > 2 else "0"
    
    version_info = f'''
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=({major}, {minor}, {patch}, 0),
        prodvers=({major}, {minor}, {patch}, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    u'040904B0',
                    [
                        StringStruct(u'CompanyName', u'VNTime JSC'),
                        StringStruct(u'FileDescription', u'Office to PDF Converter Pro'),
                        StringStruct(u'FileVersion', u'{VERSION}'),
                        StringStruct(u'InternalName', u'{APP_NAME}'),
                        StringStruct(u'LegalCopyright', u'Copyright (c) 2024 VNTime JSC'),
                        StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),
                        StringStruct(u'ProductName', u'Office to PDF Converter Pro'),
                        StringStruct(u'ProductVersion', u'{VERSION}')
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
    ]
)
'''
    
    version_file = PROJECT_ROOT / "version_info.txt"
    version_file.write_text(version_info, encoding="utf-8")
    return version_file


def get_hidden_imports():
    """Get list of hidden imports - comprehensive for all features."""
    return [
        # Core modules
        "office_converter",
        "office_converter.converters",
        "office_converter.converters.excel",
        "office_converter.converters.word",
        "office_converter.converters.ppt",
        "office_converter.converters.base",
        "office_converter.core",
        "office_converter.core.pdf_tools",
        "office_converter.utils",
        "office_converter.utils.config",
        "office_converter.utils.logging_setup",
        "office_converter.utils.localization",
        "office_converter.utils.pdf_tools",
        "office_converter.utils.com_pool",
        "office_converter.utils.history",
        "office_converter.utils.progress_estimator",
        "office_converter.utils.ocr",
        "office_converter.utils.updater",
        "office_converter.utils.libreoffice",
        "office_converter.ui",
        "office_converter.ui.main_window_pro",
        "office_converter.ui.pdf_tools_dialog",
        "office_converter.ui.pdf_tools_pro",
        "office_converter.ui.dialogs",
        
        # CustomTkinter
        "customtkinter",
        "customtkinter.windows",
        "customtkinter.windows.widgets",
        "CTkToolTip",
        
        # PIL
        "PIL",
        "PIL._tkinter_finder",
        "PIL.Image",
        "PIL.ImageTk",
        
        # Windows COM
        "pythoncom",
        "pywintypes",
        "win32com",
        "win32com.client",
        "win32api",
        "win32con",
        "win32gui",
        
        # PyMuPDF
        "fitz",
        "fitz.fitz",
        
        # Drag and drop
        "windnd",
        "tkinterdnd2",
        
        # OCR
        "pytesseract",
        "pdf2image",
        
        # Database
        "sqlite3",
        
        # Tkinter
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        
        # Standard library
        "json",
        "threading",
        "pathlib",
        "dataclasses",
        "enum",
        "typing",
        "logging",
        "subprocess",
        "urllib.request",
        "urllib.error",
    ]


def get_excludes():
    """Get modules to exclude for smaller size."""
    return [
        # Large packages we don't need
        "torch", "scipy", "numpy", "pandas", "matplotlib",
        "sklearn", "scikit-learn", "tensorflow", "keras",
        "cv2", "opencv", "opencv-python",
        "IPython", "ipython", "notebook", "jupyter", "jupyterlab",
        # Test frameworks
        "pytest", "unittest", "test", "_pytest",
        # Development tools
        "setuptools", "pip", "wheel", "distutils", "pkg_resources",
        # Crypto (not needed)
        "cryptography", "nacl", "cffi", "pycparser",
        # Other
        "docutils", "sphinx", "black", "ruff", "mypy",
        "pydoc", "doctest", "lib2to3",
    ]


def get_data_files():
    """Get data files to include."""
    data_files = []
    
    # CustomTkinter
    try:
        import customtkinter
        ctk_path = Path(customtkinter.__file__).parent
        data_files.append(f"--add-data={ctk_path};customtkinter")
        print(f"📦 Added CustomTkinter: {ctk_path}")
    except ImportError:
        print("⚠️ CustomTkinter not found")
    
    # windnd (for drag and drop)
    try:
        import windnd
        windnd_path = Path(windnd.__file__).parent
        data_files.append(f"--add-data={windnd_path};windnd")
        print(f"📦 Added windnd: {windnd_path}")
    except ImportError:
        print("⚠️ windnd not found")
    
    return data_files


def build():
    """Build the executable."""
    print(f"🔨 Building {APP_NAME} v{VERSION}...")
    print()
    
    # Ensure main script exists
    main_script_path = PROJECT_ROOT / MAIN_SCRIPT
    if not main_script_path.exists():
        # Create run_pro.py if doesn't exist
        run_script = '''
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
'''
        main_script_path.write_text(run_script)
        print(f"📝 Created entry point: {main_script_path}")
    
    # Create version info
    version_file = create_version_info()
    print(f"📝 Created version info: {version_file}")
    
    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        f"--name={APP_NAME}",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR}",
        "--clean",
        "--noupx",
    ]
    
    # Add excludes
    for mod in get_excludes():
        cmd.append(f"--exclude-module={mod}")
    
    # Add hidden imports
    for imp in get_hidden_imports():
        cmd.append(f"--hidden-import={imp}")
    
    # Add data files
    cmd.extend(get_data_files())
    
    # Add icon if exists
    icon_path = ASSETS_DIR / "icon.ico"
    if icon_path.exists():
        cmd.append(f"--icon={icon_path}")
        print(f"🎨 Using icon: {icon_path}")
    
    # Add version info
    if version_file.exists():
        cmd.append(f"--version-file={version_file}")
    
    # Add paths
    cmd.append(f"--paths={PROJECT_ROOT}")
    
    # Add main script
    cmd.append(str(main_script_path))
    
    print("📦 Running PyInstaller...")
    print(f"   Excludes: {len(get_excludes())} modules")
    print(f"   Hidden imports: {len(get_hidden_imports())} modules")
    print()
    
    # Run PyInstaller
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    
    if result.returncode == 0:
        exe_path = DIST_DIR / f"{APP_NAME}.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print()
            print("=" * 60)
            print("✅ BUILD SUCCESSFUL!")
            print(f"📁 Output: {exe_path}")
            print(f"📊 Size: {size_mb:.1f} MB")
            print("=" * 60)
        else:
            print("❌ Build failed - exe not found")
            return 1
    else:
        print(f"❌ Build failed with code {result.returncode}")
        return 1
    
    # Cleanup version file
    if version_file.exists():
        version_file.unlink()
    
    return 0


def main():
    """Main entry point."""
    if "--clean" in sys.argv:
        clean()
    elif "--help" in sys.argv:
        print(__doc__)
    else:
        sys.exit(build())


if __name__ == "__main__":
    main()
