from io import BytesIO
import zipfile
import pytest
from docx import Document
from fastapi import HTTPException
from pypdf import PdfWriter
from apps.api.app.api.v1.resumes.routes import extract_text

def _docx_bytes():
    document = Document()
    document.add_paragraph("Experienced data engineer with Python and SQL.")
    output = BytesIO()
    document.save(output)
    return output.getvalue()

def test_extracts_text_from_valid_docx():
    text, content_type = extract_text("resume.docx", _docx_bytes())
    assert "data engineer" in text
    assert content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

def test_rejects_unsupported_extension():
    with pytest.raises(HTTPException) as error:
        extract_text("resume.exe", b"not a document")
    assert error.value.status_code == 415

def test_rejects_empty_document():
    with pytest.raises(HTTPException) as error:
        extract_text("resume.pdf", b"")
    assert error.value.status_code == 400

def test_rejects_invalid_pdf_signature():
    with pytest.raises(HTTPException) as error:
        extract_text("resume.pdf", b"not a pdf")
    assert error.value.status_code == 400

def test_rejects_pdf_with_more_than_page_limit():
    writer = PdfWriter()
    for _ in range(101):
        writer.add_blank_page(width=612, height=792)
    output = BytesIO()
    writer.write(output)
    with pytest.raises(HTTPException) as error:
        extract_text("resume.pdf", output.getvalue())
    assert error.value.status_code == 413

def test_rejects_docx_archive_with_excessive_compression_ratio():
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "A" * 100_000)
        archive.writestr("word/document.xml", "B" * 100_000)
    with pytest.raises(HTTPException) as error:
        extract_text("resume.docx", output.getvalue())
    assert error.value.status_code == 413

def test_rejects_incomplete_docx_package():
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", "<document/>")
    with pytest.raises(HTTPException) as error:
        extract_text("resume.docx", output.getvalue())
    assert error.value.status_code == 400
