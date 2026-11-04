import re
import zipfile
from io import BytesIO
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from pypdf import PdfReader
from docx import Document
from packages.storage.objects import store_private_object, delete_private_object
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import ResumeDocument, AuditLog
from apps.api.app.core.redis_limits import enforce_rate_limit

router = APIRouter()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_EXTRACTED_CHARS = 500_000
MAX_PDF_PAGES = 100
MAX_DOCX_ENTRIES = 1_000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
ALLOWED = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".md": "text/markdown", ".markdown": "text/markdown", ".txt": "text/plain",
}

def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=415, detail="Supported formats are PDF, DOCX, Markdown and plain text")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded document is empty")

    if suffix in {".md", ".markdown", ".txt"}:
        try:
            text = data.decode("utf-8-sig", errors="strict").replace("\\x00", "")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Text documents must use UTF-8 encoding") from exc
        normalized = re.sub(r"\\r\\n?", "\\n", text)
        return normalized[:MAX_EXTRACTED_CHARS], ALLOWED[suffix]

    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF")
        try:
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise HTTPException(status_code=400, detail="Password-protected PDFs are not supported")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise HTTPException(status_code=413, detail=f"PDF exceeds the {MAX_PDF_PAGES}-page limit")
            parts, total = [], 0
            for page in reader.pages:
                remaining = MAX_EXTRACTED_CHARS - total
                if remaining <= 0:
                    break
                page_text = page.extract_text() or ""
                parts.append(page_text[:remaining])
                total += min(len(page_text), remaining)
            return " ".join(parts), ALLOWED[suffix]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Unable to safely read this PDF") from exc

    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise HTTPException(status_code=413, detail="DOCX contains too many archive entries")
            if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                raise HTTPException(status_code=400, detail="The uploaded DOCX package is incomplete")
            uncompressed = sum(item.file_size for item in entries)
            if uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise HTTPException(status_code=413, detail="DOCX expands beyond the 50 MB safety limit")
            for item in entries:
                if item.file_size > 0 and item.file_size / max(item.compress_size, 1) > MAX_DOCX_COMPRESSION_RATIO:
                    raise HTTPException(status_code=413, detail="DOCX compression ratio exceeds the safety limit")
        document = Document(BytesIO(data))
        parts, total = [], 0
        for paragraph in document.paragraphs:
            if total >= MAX_EXTRACTED_CHARS:
                break
            value = paragraph.text
            remaining = MAX_EXTRACTED_CHARS - total
            parts.append(value[:remaining])
            total += min(len(value), remaining)
        return " ".join(parts), ALLOWED[suffix]
    except HTTPException:
        raise
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail="Unable to safely read this DOCX document") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to read this DOCX document") from exc

@router.post("", status_code=201)
async def upload_resume(file: UploadFile = File(...), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    enforce_rate_limit(f"resume-upload:{user.id}", limit=10, window_seconds=3600)
    filename = Path(file.filename or "resume").name
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Resume exceeds the 10 MB upload limit")
    extracted, content_type = extract_text(filename, data)
    stored = store_private_object(
        data, filename, content_type, owner_scope=str(user.id),
    )
    try:
        row = ResumeDocument(
            user_id=user.id, filename=filename[:255], content_type=content_type,
            storage_key=stored["object_key"], extracted_text=extracted, version=1,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        try:
            delete_private_object(stored["object_key"])
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Unable to clean up failed resume upload", extra={"user_id": user.id}
            )
        raise
    return {"id": row.id, "filename": row.filename, "content_type": row.content_type,
            "version": row.version, "extracted_characters": len(extracted)}

@router.get("")
def list_resumes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ResumeDocument).where(ResumeDocument.user_id == user.id)
                      .order_by(ResumeDocument.created_at.desc())).all()
    return [{"id": r.id, "filename": r.filename, "content_type": r.content_type,
             "version": r.version, "created_at": r.created_at} for r in rows]

@router.get("/{resume_id}/text")
def resume_text(resume_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    row = db.scalar(select(ResumeDocument).where(
        ResumeDocument.id == resume_id, ResumeDocument.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"id": row.id, "filename": row.filename, "text": row.extracted_text}

class ATSRequest(BaseModel):
    job_description: str = Field(min_length=20, max_length=30000)

@router.post("/{resume_id}/analyze")
def analyze_resume(resume_id: int, body: ATSRequest, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    row = db.scalar(select(ResumeDocument).where(
        ResumeDocument.id == resume_id, ResumeDocument.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    terms = sorted({term.lower() for term in re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,}", body.job_description)
                    if len(term) > 2})
    resume = row.extracted_text.lower()
    matched = [term for term in terms if term in resume]
    missing = [term for term in terms if term not in resume]
    score = round(100 * len(matched) / max(1, len(terms)))
    return {"resume_id": row.id, "method": "transparent_keyword_coverage",
            "coverage_score": score, "matched_terms": matched[:100],
            "missing_terms": missing[:100],
            "warning": "Heuristic keyword coverage only. It is not a commercial ATS score and does not assess context or truthfulness."}

@router.delete("/{resume_id}", status_code=204)
def delete_resume(resume_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    row = db.scalar(select(ResumeDocument).where(
        ResumeDocument.id == resume_id, ResumeDocument.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")

    object_key = row.storage_key
    db.add(AuditLog(user_id=user.id, action="resume.deleted",
                    resource_type="resume", resource_id=str(row.id)))
    db.delete(row)
    db.commit()
    try:
        delete_private_object(object_key)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Unable to remove deleted resume object", extra={"user_id": user.id}
        )
    return None
