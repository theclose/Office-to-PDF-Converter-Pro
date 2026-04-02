# -*- mode: python ; coding: utf-8 -*-
# OfficeToPDF Pro - PyInstaller Build Spec
# Build command: pyinstaller OfficeToPDF_Pro.spec --clean

import os
import sys

# Paths
PROJECT_ROOT = os.path.abspath('.')
# Dynamic site-packages path (works on any build environment)
import importlib
SITE_PACKAGES = os.path.dirname(os.path.dirname(importlib.import_module('customtkinter').__file__))

a = Analysis(
    [os.path.join(PROJECT_ROOT, 'run_pro.py')],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        # CustomTkinter (required for UI)
        (os.path.join(SITE_PACKAGES, 'customtkinter'), 'customtkinter'),
        # CTkToolTip (tooltips)
        (os.path.join(SITE_PACKAGES, 'CTkToolTip'), 'CTkToolTip'),
        # TkinterDnD2 (drag & drop)
        (os.path.join(SITE_PACKAGES, 'tkinterdnd2'), 'tkinterdnd2'),
        # windnd (alternative drag & drop)
        (os.path.join(SITE_PACKAGES, 'windnd'), 'windnd'),
        # Project assets
        (os.path.join(PROJECT_ROOT, 'locales'), 'locales'),
    ],
    hiddenimports=[
        # Project modules — Layer 1: Converters
        'office_converter',
        'office_converter.converters',
        'office_converter.converters.base',
        'office_converter.converters.excel',
        'office_converter.converters.word',
        'office_converter.converters.ppt',
        'office_converter.converters.libreoffice',
        # Layer 2: Core
        'office_converter.core',
        'office_converter.core.engine',
        'office_converter.core.pdf_tools',
        'office_converter.core.excel_tools',
        'office_converter.core.pdf',
        'office_converter.core.pdf.common',
        'office_converter.core.pdf.compression',
        'office_converter.core.pdf.pages',
        'office_converter.core.pdf.security',
        'office_converter.core.pdf.watermark',
        'office_converter.core.pdf.conversion',
        'office_converter.core.pdf.merge_split',
        # Layer 3: UI + Mixins
        'office_converter.ui',
        'office_converter.ui.main_window_pro',
        'office_converter.ui.conversion_mixin',
        'office_converter.ui.dialogs_mixin',
        'office_converter.ui.pdf_tools_pro',
        'office_converter.ui.pdf_tools_ops_mixin',
        'office_converter.ui.excel_tools_ui',
        'office_converter.ui.excel_tools_ops_mixin',
        'office_converter.ui.file_tools_ui_v2',
        # Layer 4: Utils
        'office_converter.utils',
        'office_converter.utils.config',
        'office_converter.utils.logging_setup',
        'office_converter.utils.localization',
        'office_converter.utils.com_pool',
        'office_converter.utils.recent_files',
        'office_converter.utils.progress_estimator',
        'office_converter.utils.watchdog',
        'office_converter.utils.tkdnd_wrapper',
        'office_converter.utils.dnd_helpers',
        'office_converter.utils.pdf_tools',
        'office_converter.utils.history',
        'office_converter.utils.updater',
        'office_converter.utils.parallel_converter',
        # Third-party
        'customtkinter',
        'CTkToolTip',
        'PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk',
        'openpyxl', 'openpyxl.workbook', 'openpyxl.worksheet', 'openpyxl.utils',
        'pythoncom', 'pywintypes',
        'win32com', 'win32com.client', 'win32api', 'win32con', 'win32gui',
        'fitz', 'fitz.fitz',
        'windnd',
        'tkinterdnd2',
        'sqlite3',
        # Stdlib
        'tkinter', 'tkinter.ttk', 'tkinter.filedialog', 'tkinter.messagebox',
        'json', 'threading', 'pathlib', 'dataclasses', 'enum', 'typing',
        'logging', 'subprocess', 'urllib.request', 'urllib.error',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Heavy science/ML libs (not needed)
        'torch', 'scipy', 'numpy', 'pandas', 'matplotlib',
        'sklearn', 'scikit-learn', 'tensorflow', 'keras',
        'cv2', 'opencv', 'opencv-python',
        # Dev tools
        'IPython', 'ipython', 'notebook', 'jupyter', 'jupyterlab',
        'pytest', 'unittest', 'test', '_pytest',
        'setuptools', 'pip', 'wheel', 'distutils', 'pkg_resources',
        'cryptography', 'nacl', 'cffi', 'pycparser',
        'docutils', 'sphinx', 'black', 'ruff', 'mypy',
        'pydoc', 'doctest', 'lib2to3',
        # OCR (optional, not bundled — requires separate Tesseract install)
        'office_converter.utils.ocr', 'pytesseract', 'pdf2image',
        # Dead project code
        'grid', 'scripts',
    ],
    noarchive=False,
    optimize=1,  # Optimize bytecode (-O flag)
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='OfficeToPDF_Pro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
