"""Module 1 - Document ingestion.

Extracts text from PDF (PyMuPDF), DOCX (python-docx) and TXT/MD files while
preserving heading structure as "blocks": {"text": str, "heading": bool}.
"""
import io
import re
from statistics import median


class ParseError(ValueError):
    pass


def _clean(text: str) -> str:
    text = text.replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl")
    return re.sub(r"[ \t ]+", " ", text).strip()


def _parse_pdf(data: bytes) -> list[dict]:
    try:
        import pymupdf  # PyMuPDF >= 1.24
    except ImportError:  # pragma: no cover - older releases
        import fitz as pymupdf

    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ParseError("This PDF could not be opened. Is the file corrupted or password-protected?") from exc

    lines: list[tuple[str, float, bool]] = []
    for page in doc:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
                if not spans:
                    continue
                text = _clean("".join(s["text"] for s in line["spans"]))
                if not text:
                    continue
                size = max(s.get("size", 0) for s in spans)
                bold = all((s.get("flags", 0) & 16) or "bold" in s.get("font", "").lower() for s in spans)
                lines.append((text, size, bold))
            lines.append(("", 0, False))  # block boundary
    doc.close()

    sizes = [s for t, s, _ in lines if t for _ in range(max(1, len(t) // 20))]
    if not sizes:
        raise ParseError(
            "No selectable text was found in this PDF. Scanned/image-only PDFs need OCR first "
            "- try exporting it as a text PDF or paste the text instead."
        )
    body = median(sizes)

    blocks: list[dict] = []
    for text, size, bold in lines:
        if not text:
            blocks.append({"text": "", "heading": False})
            continue
        if re.fullmatch(r"(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?", text, re.I):
            continue  # page numbers
        words = len(text.split())
        heading = words <= 14 and (size >= body * 1.12 or (bold and not text.endswith((".", ",", ";"))))
        blocks.append({"text": text, "heading": heading})
    return blocks


def _parse_docx(data: bytes) -> list[dict]:
    try:
        import docx
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ParseError("This DOCX file could not be opened.") from exc

    blocks: list[dict] = []
    for para in document.paragraphs:
        text = _clean(para.text)
        if not text:
            continue
        style = (para.style.name or "").lower() if para.style is not None else ""
        runs = [r for r in para.runs if r.text.strip()]
        all_bold = bool(runs) and all(r.bold for r in runs)
        words = len(text.split())
        heading = style.startswith(("heading", "title")) or (
            all_bold and words <= 14 and not text.endswith((".", ","))
        )
        blocks.append({"text": text, "heading": heading})
        blocks.append({"text": "", "heading": False})
    for table in document.tables:
        for row in table.rows:
            cells = []
            for cell in row.cells:
                t = _clean(cell.text)
                if t and t not in cells:
                    cells.append(t)
            if cells:
                blocks.append({"text": " - ".join(cells), "heading": False})
                blocks.append({"text": "", "heading": False})
    return blocks


def _parse_text(data: bytes) -> list[dict]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="ignore")
    blocks = []
    for raw in text.splitlines():
        line = _clean(raw)
        md = re.match(r"^#{1,4}\s+(.*)$", line)
        if md:
            blocks.append({"text": md.group(1).strip("# "), "heading": True})
        else:
            blocks.append({"text": line, "heading": False})
    return blocks


def parse_document(filename: str, data: bytes) -> list[dict]:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        blocks = _parse_pdf(data)
    elif name.endswith(".docx"):
        blocks = _parse_docx(data)
    elif name.endswith(".doc"):
        raise ParseError("Legacy .doc files are not supported - save the file as .docx or PDF.")
    elif name.endswith((".txt", ".md", "")):
        blocks = _parse_text(data)
    else:
        raise ParseError("Unsupported file type. Upload a PDF, DOCX or TXT file.")
    if sum(len(b["text"].split()) for b in blocks) < 25:
        raise ParseError("The document has too little text to extract topics from (need at least a few sentences).")
    return blocks
