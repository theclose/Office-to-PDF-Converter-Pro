# Office to PDF Converter Pro

[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)](https://github.com/vntimejsc-code/Office-to-PDF-Converter-Pro)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Professional-grade Office document to PDF converter with modern UI and advanced features.

## ✨ Features

### Core Conversion
- **Multi-Format Support**: Excel (.xlsx, .xls), Word (.docx, .doc), PowerPoint (.pptx, .ppt)
- **Batch Processing**: Convert multiple files at once with progress tracking
- **High Quality**: Native Office conversion preserves formatting, fonts, and layout
- **Scan Mode**: Convert PDFs to image-based format for archival

### PDF Tools
- 📄 **Merge**: Combine multiple PDFs into one
- ✂️ **Split**: Extract specific pages
- 🔄 **Rotate**: Rotate pages by 90°/180°/270°
- 📦 **Compress**: Reduce file size
- 🔒 **Protect**: Add password encryption
- 💧 **Watermark**: Add text/image watermarks
- 🖼️ **Convert**: PDF ↔ Images

### User Experience
- 🎨 **Modern UI**: CustomTkinter with dark/light themes
- 📁 **Drag & Drop**: Drop files directly into the app
- 👁️ **PDF Preview**: Preview converted PDFs
- 🕐 **Recent Files**: Quick access to recently used files
- ⌨️ **Keyboard Shortcuts**: Ctrl+O, Enter, Escape, etc.
- 🔄 **Auto-Update**: Check for new versions from GitHub

## 📋 Requirements

- Windows 10/11
- Python 3.10+
- Microsoft Office installed (Excel, Word, PowerPoint)

## 🚀 Installation

```bash
# Clone repository
git clone https://github.com/vntimejsc-code/Office-to-PDF-Converter-Pro.git
cd Office-to-PDF-Converter-Pro

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## 💻 Usage

### GUI Application (Recommended)

```bash
# Modern Pro UI (v4.0.0)
python -m office_converter.ui.main_window_pro

# CustomTkinter UI (v3.x)
python -m office_converter.ui.main_window_ctk

# Classic Tkinter UI (v2.x)
python -m office_converter.ui.main_window
```

### Build Standalone .exe

```bash
python build_exe.py
# Output: dist/OfficeToPDF_Pro.exe
```

### Run Tests

```bash
pytest tests/ -v
```

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Add files |
| `Enter` | Start conversion |
| `Escape` | Stop conversion |
| `Delete` | Clear file list |
| `F1` | Show shortcuts |

## ⚙️ Configuration

Configuration is stored in `config.json`:

```json
{
  "language": "vi",
  "theme": "dark",
  "pdf_quality": 0,
  "auto_open_folder": true
}
```

| Key | Values | Description |
|-----|--------|-------------|
| `language` | `vi`, `en`, `zh` | UI language |
| `pdf_quality` | `0` (high), `1` (compact) | PDF output quality |
| `theme` | `light`, `dark` | UI theme |
| `auto_open_folder` | `true`, `false` | Open folder after conversion |

## 🏗️ Architecture

```
office_converter/
├── converters/           # COM-based Office converters
│   ├── excel.py          # Excel → PDF
│   ├── word.py           # Word → PDF
│   └── ppt.py            # PowerPoint → PDF
├── ui/
│   ├── main_window_pro.py   # Pro UI v4.0 (recommended)
│   ├── main_window_ctk.py   # CustomTkinter UI v3.x
│   ├── main_window.py       # Classic Tkinter UI
│   └── pdf_tools_dialog.py  # PDF Tools dialog
├── utils/
│   ├── config.py         # Configuration manager
│   ├── pdf_tools.py      # PDF manipulation (PyMuPDF)
│   ├── com_pool.py       # COM object pooling
│   ├── updater.py        # Auto-update checker
│   └── logging_setup.py  # Rotating log files
├── tests/                # Pytest test suite
├── build_exe.py          # PyInstaller build script
└── requirements.txt      # Dependencies
```

## 📊 Version History

| Version | Features |
|---------|----------|
| **4.0.0** | Pro UI with PDF Preview, SQLite history, Drag & Drop |
| 3.1.0 | Animations, context-aware options, file type indicators |
| 3.0.0 | CustomTkinter UI modernization |
| 2.1.0 | Checkmarks for completed files, version in title |
| 2.0.0 | COM pool, rotating logs, exception handling fixes |

## 📝 License

MIT License - Copyright (c) 2024 TungDo
