# Office to PDF Converter Pro

Professional-grade Office document to PDF converter using COM automation.

## Features

- **Multi-Format**: Excel (.xlsx, .xls), Word (.docx, .doc), PowerPoint (.pptx, .ppt)
- **PDF Tools**: Merge, Split, Rotate, Compress, Protect, Watermark
- **Batch Processing**: Convert multiple files at once
- **High Quality**: Preserves formatting, fonts, and layout

## Requirements

- Windows 10/11
- Python 3.10+
- Microsoft Office installed (Excel, Word, PowerPoint)

## Installation

```bash
# Clone repository
git clone https://github.com/vntimejsc-code/Office-to-PDF-Converter-Pro.git
cd Office-to-PDF-Converter-Pro

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install pywin32 pymupdf pillow pytest
```

## Usage

### GUI Application
```bash
python -m office_converter.ui.main_window
```

### Run Tests
```bash
pytest tests/ -v
```

### Module Test
```bash
python -m office_converter.main
```

## Configuration

Configuration is stored in `config.json`:

```json
{
  "language": "vi",
  "theme": "light",
  "pdf_quality": 0
}
```

| Key | Values | Description |
|-----|--------|-------------|
| `language` | `vi`, `en`, `zh` | UI language |
| `pdf_quality` | `0` (high), `1` (low) | PDF output quality |
| `theme` | `light`, `dark` | UI theme |

## Architecture

```
office_converter/
├── converters/     # COM-based Office converters
├── core/           # PDF manipulation (PyMuPDF)
├── ui/             # Tkinter GUI
├── utils/          # Config, logging, COM pool
└── tests/          # Pytest test suite
```

## License

MIT License
