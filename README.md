# Text to PDF Converter

A simple command-line tool to convert EUC-JP encoded text files to A4 PDF with a 2UP layout.

## Features
- Converts EUC-JP text to PDF
- 2UP layout (2 columns per page, Landscape) or 1UP (1 column, Portrait)
- Custom headers and footers ("Printed by <User>")
- Automatic text wrapping for long lines (CJK-aware)
- Automatic text wrapping for long lines (CJK-aware)
- Font size selection (large, medium, small)
- **Monospaced Rendering**: Uses `Courier` for ASCII/English and `HeiseiMin-W3` for Japanese to ensure perfect alignment for code and tables.

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run conversion (Default: 2UP, Medium font)
./text2pdf input.txt output.pdf

# Specify font size
./text2pdf input.txt output.pdf --font-size large

# Specify layout (1UP = Portrait)
./text2pdf input.txt output.pdf --layout 1up

# Run with sample files
./text2pdf samples/english_sample.txt output_english.pdf
./text2pdf samples/mixed_sample_euc.txt output_mixed.pdf
```

## Requirements
- Python 3
- reportlab
