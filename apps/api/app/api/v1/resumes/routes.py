import re
import zipfile
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from pypdf import PdfReader
from docx import Document
from apps.api.app.core.config import get_settings
from apps.api.app.dependencies import get_current_user, get_db
from packages.database.models.identity import User
from packages.database.models.career import ResumeDocument

router = APIRouter()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED = {".pdf": "application/pdf",
           ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

def extract_text(filename: str, data: bytes) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise HTTPException(status_code=415, detail="Only PDF and DOCX files are supported")
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF")
        try:
            text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Unable to read this PDF") from exc
        return text[:500000], ALLOWED[suffix]
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Missing document XML")
        document = Document(BytesIO(data))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Unable to read this DOCX document") from exc
    return text[:500000], ALLOWED[suffix]

@router.post("", status_code=201)
async def upload_resume(file: UploadFile = File(...), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    filename = Path(file.filename or "resume").name
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Resume exceeds the 10 MB upload limit")
    extracted, content_type = extract_text(filename, data)
    root = Path(get_settings().storage_path).resolve()
    user_dir = (root / str(user.id)).resolve()
    user_dir.mkdir(parents=True, exist_ok=True)
    if root not in user_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid storage location")
    stored_name = uuid4().hex + Path(filename).suffix.lower()
    destination = user_dir / stored_name
    destination.write_bytes(data)
    row = ResumeDocument(user_id=user.id, filename=filename[:255], content_type=content_type,
                         storage_key=f"{user.id}/{stored_name}", extracted_text=extracted, version=1)
    db.add(row)
    db.commit()
    db.refresh(row)
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
