# Text to PDF Converter

A simple command-line tool to convert EUC-JP encoded text files to A4 PDF with a 2UP layout.

## Features
- Converts EUC-JP text to PDF
- 2UP layout (2 columns per page)
- Custom headers and footers
- Automatic text wrapping for long lines (CJK-aware)
- Font size selection (large, medium, small)

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run conversion
python text2pdf.py input.txt output.pdf

# Specify font size (default: medium)
python text2pdf.py input.txt output.pdf --font-size large
python text2pdf.py input.txt output.pdf --font-size small
```

## Requirements
- Python 3
- reportlab
