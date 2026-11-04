"""Optional OCR helpers with bounded image and PDF rendering."""
from __future__ import annotations
from io import BytesIO

MAX_IMAGE_PIXELS = 40_000_000
MAX_OCR_PAGES = 30

def ocr_image(data: bytes) -> str:
    try:
        from PIL import Image, ImageOps
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('Install document OCR dependencies and the Tesseract binary') from exc
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > MAX_IMAGE_PIXELS:
            raise ValueError("Image exceeds the OCR pixel limit")
        image = ImageOps.exif_transpose(image).convert("RGB")
        return pytesseract.image_to_string(image, timeout=30)[:500_000]

def ocr_pdf(data: bytes, max_pages: int = MAX_OCR_PAGES) -> str:
    try:
        import fitz
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise RuntimeError('Install document OCR dependencies and the Tesseract binary') from exc
    document = fitz.open(stream=data, filetype="pdf")
    if document.page_count > max_pages:
        raise ValueError(f"OCR PDF exceeds the {max_pages}-page limit")
    parts = []
    total = 0
    try:
        for page in document:
            if page.rect.width * page.rect.height * 2.25 > MAX_IMAGE_PIXELS:
                raise ValueError("PDF page dimensions exceed the OCR pixel limit")
            pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            if pixmap.width * pixmap.height > MAX_IMAGE_PIXELS:
                raise ValueError("Rendered PDF page exceeds the OCR pixel limit")
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            text = pytesseract.image_to_string(image, timeout=30)
            parts.append(text[:max(0, 500_000 - total)])
            total += len(parts[-1])
            if total >= 500_000:
                break
    finally:
        document.close()
    return "\n".join(parts)
