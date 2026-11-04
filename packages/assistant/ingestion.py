"""Document, image and source-code normalization for assistant knowledge ingestion."""
from __future__ import annotations
import ast
from io import BytesIO
from pathlib import Path

MAX_BYTES = 12 * 1024 * 1024
TEXT_EXTENSIONS = {".txt", ".md", ".rst", ".json", ".yaml", ".yml", ".toml", ".csv", ".log"}
CODE_EXTENSIONS = {".py"}

def _python_ast(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    sections = ["PYTHON SOURCE INDEX"]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            segment = ast.get_source_segment(source, node) or ""
            signature = ast.get_source_segment(source, node.args) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else ""
            doc = ast.get_docstring(node) or ""
            sections.append(f"{node.__class__.__name__} {node.name} {signature or ''}\n{doc}\n{segment[:6000]}")
    return "\n\n".join(sections)[:100000] or source

def parse_document(filename: str, content_type: str, payload: bytes) -> str:
    if not payload:
        raise ValueError("The uploaded file is empty")
    if len(payload) > MAX_BYTES:
        raise ValueError("The uploaded file exceeds the 12 MB limit")
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages[:100]]
        return "\n\n".join(pages)[:100000]
    if suffix == ".docx" or content_type.endswith("wordprocessingml.document"):
        from docx import Document
        document = Document(BytesIO(payload))
        return "\n".join(p.text for p in document.paragraphs)[:100000]
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"} or content_type.startswith("image/"):
        try:
            from PIL import Image
            import pytesseract
            image = Image.open(BytesIO(payload)).convert("RGB")
            return pytesseract.image_to_string(image)[:100000]
        except ImportError as exc:
            raise ValueError("Image OCR requires the optional Pillow and pytesseract packages plus a Tesseract binary") from exc
    if suffix in CODE_EXTENSIONS:
        source = payload.decode("utf-8", errors="replace")
        return _python_ast(source)
    if suffix in TEXT_EXTENSIONS or content_type.startswith("text/"):
        return payload.decode("utf-8", errors="replace")[:100000]
    raise ValueError("Unsupported file type. Upload PDF, DOCX, image, text, Markdown or Python source.")
