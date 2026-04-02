# Office to PDF Converter Pro

[![Version](https://img.shields.io/badge/version-4.2.x-blue.svg)](https://github.com/vntimejsc-code/Office-to-PDF-Converter-Pro)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Professional-grade Office document to PDF converter with modern UI, COM pooling, and advanced PDF tools.

## ✨ Features

### Core Conversion
- **Multi-Format Support**: Excel (.xlsx, .xls), Word (.docx, .doc), PowerPoint (.pptx, .ppt)
- **Batch Processing**: Convert multiple files with progress tracking & ETA
- **5 Quality Presets**: Maximum → Compact, with DPI & compression control
- **Scan Mode**: Convert to image-based PDF for archival (configurable DPI)
- **COM Pool**: Reuses Office instances for 3–5× faster batch conversion

### PDF Tools
- 📄 **Merge** — Combine multiple PDFs into one
- ✂️ **Split** — Extract specific pages or page ranges
- 🔄 **Rotate** — Rotate pages by 90°/180°/270°
- 📦 **Compress** — Reduce file size (5 quality levels)
- 🔒 **Protect** — Add password encryption (user + owner)
- 💧 **Watermark** — Add text watermarks with customization
- 🖼️ **Convert** — PDF ↔ Images (PNG/JPEG)

### File Tools
- 📝 **Batch Rename** — Rules: case, replace, trim, sequence, accents
- 🔍 **Duplicate Finder** — Size → Quick Hash → Full Hash
- 📁 **Empty Folder Cleaner** — Find and remove empty directories
- 📅 **Attribute Manager** — Modify timestamps and file attributes

### User Experience
- 🎨 **Modern UI**: CustomTkinter with dark/light themes
- 📁 **Drag & Drop**: Drop files directly into the app (tkinterdnd2 + windnd)
- 🕐 **Recent Files**: SQLite-backed quick access
- ⌨️ **Keyboard Shortcuts**: Ctrl+O, Enter, Escape, Delete, F1
- 🌐 **Multi-language**: Vietnamese, English, Chinese, Japanese, Korean
- 🔄 **Auto-Update**: GitHub release checker

## 📋 Requirements

- **OS**: Windows 10/11
- **Python**: 3.11+
- **Microsoft Office**: Excel, Word, PowerPoint (for conversion)

## 🚀 Installation

```bash
# Clone repository
git clone https://github.com/vntimejsc-code/Office-to-PDF-Converter-Pro.git
cd Office-to-PDF-Converter-Pro

# Install dependencies
pip install -r requirements.txt
```

## 💻 Usage

### Run Application

```bash
python run_pro.py
```

### Build Standalone EXE

```bash
pyinstaller OfficeToPDF_Pro.spec --clean
# Output: dist/OfficeToPDF_Pro.exe (~44 MB)
```

### Run Tests

```bash
python -m pytest tests/ -v --tb=short
# Baseline: 188+ passed, 4 skipped
```

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Add files |
| `Enter` | Start conversion |
| `Escape` | Stop conversion |
| `Delete` | Clear file list |
| `F1` | Show shortcuts |

## 🏗️ Architecture

```
office_converter/
├── converters/              # COM-based Office converters
│   ├── base.py              # Abstract base + COM ref counting
│   ├── excel.py             # Excel → PDF (3 export methods)
│   ├── word.py              # Word → PDF (3 export methods)
│   ├── ppt.py               # PowerPoint → PDF
│   └── libreoffice.py       # LibreOffice fallback
├── core/
│   ├── engine.py            # Conversion engine + batch orchestration
│   ├── file_tools.py        # Rename rules, duplicates, attributes
│   ├── excel_tools.py       # Excel sheet operations
│   ├── pdf_tools.py         # PDF tool orchestration
│   └── pdf/                 # PDF processing modules
│       ├── compression.py   # Multi-strategy compression
│       ├── merge_split.py   # Merge & split operations
│       ├── security.py      # Password protection
│       ├── watermark.py     # Text watermarks
│       ├── conversion.py    # PDF ↔ Image conversion
│       └── pages.py         # Page rotation & extraction
├── ui/
│   ├── main_window_pro.py   # Main Pro UI window
│   ├── conversion_mixin.py  # Conversion logic mixin
│   ├── dialogs_mixin.py     # Dialog management mixin
│   ├── pdf_tools_pro.py     # PDF Tools tab
│   ├── excel_tools_ui.py    # Excel Tools tab
│   └── file_tools_ui_v2.py  # File Tools tab
├── utils/
│   ├── com_pool.py          # COM object pooling + zombie detection
│   ├── config.py            # JSON config with auto-save
│   ├── localization.py      # i18n (5 languages)
│   ├── logging_setup.py     # Rotating log files
│   ├── recent_files.py      # SQLite recent files DB
│   └── watchdog.py          # File system monitor
├── locales/                 # Language JSON files
├── tests/                   # 14 test files (188+ tests)
├── docs/                    # Architecture, guides, known traps
├── OfficeToPDF_Pro.spec     # PyInstaller build spec
└── run_pro.py               # Entry point
```

## 📊 Quality System

| Preset | COM Export | DPI | Compression |
|--------|-----------|-----|-------------|
| ⭐ Maximum | Print | 300 | None |
| 🔵 High | Print | 300 | Light |
| 🟢 Balanced | Print | 300 | Medium |
| 🟡 Compact | Screen | 96 | Heavy |
| ⚙️ Custom | User DPI | — | User choice |

## 📝 License

MIT License — Copyright (c) 2024 TungDo
