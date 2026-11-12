"""Raw text extraction from PDF pages.

Two layout-based backends are compared (see eval/):
  - "pdfplumber": pdfminer layout analysis, keeps butir numbers inline with their text.
  - "pymupdf":    MuPDF text layer, sorted by position.
Both read the PDF's existing text layer. For UU 19/2016 and UU 1/2024 that layer is
OCR embedded by the publisher (scans), so OCR noise is handled in clean.py.
An optional "tesseract" backend re-OCRs the page images when Tesseract is installed.
"""
from __future__ import annotations

import shutil
from pathlib import Path

METHODS = ("pdfplumber", "pymupdf", "tesseract")


def extract_pages(pdf_path: str | Path, method: str = "pdfplumber") -> list[str]:
    pdf_path = str(pdf_path)
    if method == "pdfplumber":
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            return [(p.extract_text() or "") for p in pdf.pages]
    if method == "pymupdf":
        import pymupdf

        pymupdf.TOOLS.mupdf_display_errors(False)
        with pymupdf.open(pdf_path) as doc:
            return [p.get_text("text", sort=True) for p in doc]
    if method == "tesseract":
        return _tesseract_pages(pdf_path)
    raise ValueError(f"unknown method {method!r}; choose from {METHODS}")


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _tesseract_pages(pdf_path: str) -> list[str]:
    """Re-OCR every page at 300 dpi with Tesseract (lang 'ind' if installed)."""
    import subprocess
    import tempfile

    import pymupdf

    if not tesseract_available():
        raise RuntimeError("tesseract binary not found on PATH")
    langs = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    lang = "ind" if "\nind" in langs else "eng"
    out = []
    with pymupdf.open(pdf_path) as doc, tempfile.TemporaryDirectory() as tmp:
        for i, page in enumerate(doc):
            png = Path(tmp) / f"p{i}.png"
            page.get_pixmap(dpi=300).save(png)
            res = subprocess.run(
                ["tesseract", str(png), "stdout", "-l", lang, "--psm", "4"],
                capture_output=True, text=True, encoding="utf-8",
            )
            out.append(res.stdout)
    return out
