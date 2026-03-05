from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _extract_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _extract_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "PDF support requires 'pypdf'. Install it with: pip install pypdf"
        ) from exc

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def _extract_docx(path: Path) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise RuntimeError(
            "DOCX support requires 'python-docx'. Install it with: pip install python-docx"
        ) from exc

    document = Document(str(path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return "\n".join(paragraphs)


def extract_bronze(doc_path: Path) -> dict[str, Any]:
    if not doc_path.exists():
        raise FileNotFoundError(f"Document not found: {doc_path}")

    suffix = doc_path.suffix.lower()
    if suffix == ".txt":
        extracted_text = _extract_txt(doc_path)
        extractor = "txt_reader"
    elif suffix == ".pdf":
        extracted_text = _extract_pdf(doc_path)
        extractor = "pypdf"
    elif suffix == ".docx":
        extracted_text = _extract_docx(doc_path)
        extractor = "python_docx"
    else:
        raise ValueError("Unsupported file type. Use .txt, .pdf, or .docx")

    stat = doc_path.stat()
    return {
        "source": {
            "path": str(doc_path),
            "name": doc_path.name,
            "extension": suffix,
            "size_bytes": stat.st_size,
            "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        },
        "extracted_text": extracted_text,
        "tables": [],
        "metadata": {
            "extractor": extractor,
            "extracted_utc": datetime.now(tz=timezone.utc).isoformat(),
            "version": "0.1",
        },
    }
