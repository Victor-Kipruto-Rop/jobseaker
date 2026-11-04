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
from packages.database.models.career import ResumeDocument, AuditLog, GeneratedArtifact, CandidateOpportunity
from apps.api.app.core.redis_limits import enforce_rate_limit
from packages.resumes.tailoring import tailor_resume
from packages.resumes.cover_letter import build_cover_letter

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
            text = data.decode("utf-8-sig", errors="strict").replace("\x00", "")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Text documents must use UTF-8 encoding") from exc
        normalized = re.sub(r"\r\n?", "\n", text)
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


class TailorRequest(BaseModel):
    job_description: str = Field(min_length=20, max_length=30000)

@router.post("/{resume_id}/tailor")
def tailor_resume_for_role(resume_id: int, body: TailorRequest,
                           user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    """Return a reviewable relevance ordering without altering the stored resume."""
    enforce_rate_limit(f"resume-tailor:{user.id}", limit=20, window_seconds=3600)
    row = db.scalar(select(ResumeDocument).where(
        ResumeDocument.id == resume_id, ResumeDocument.user_id == user.id))
    if not row:
        raise HTTPException(status_code=404, detail="Resume not found")
    try:
        proposal = tailor_resume(row.extracted_text, body.job_description)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.add(AuditLog(user_id=user.id, action="resume.tailoring_proposed",
                    resource_type="resume", resource_id=str(row.id)))
    db.commit()
    return {"resume_id": row.id, "filename": row.filename, **proposal}


class CoverLetterRequest(BaseModel):
    job_description: str = Field(min_length=20, max_length=30000)
    role_title: str = Field(min_length=2, max_length=250)
    company_name: str = Field(default="", max_length=250)
    opportunity_id: int | None = None

@router.post("/{resume_id}/cover-letter", status_code=201)
def create_cover_letter(resume_id: int, body: CoverLetterRequest,
                        user: User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """Save an evidence-grounded cover-letter draft for candidate editing."""
    enforce_rate_limit(f"cover-letter:{user.id}", limit=10, window_seconds=3600)
    resume = db.scalar(select(ResumeDocument).where(
        ResumeDocument.id == resume_id, ResumeDocument.user_id == user.id))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    opportunity = None
    if body.opportunity_id is not None:
        opportunity = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.id == body.opportunity_id,
            CandidateOpportunity.user_id == user.id))
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")
    try:
        draft = build_cover_letter(resume.extracted_text, body.job_description,
                                   body.role_title, body.company_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    artifact = GeneratedArtifact(
        user_id=user.id, artifact_type="cover_letter", title=draft["title"],
        content=draft["content"], source_resume_id=resume.id,
        source_opportunity_id=opportunity.id if opportunity else None,
        status="draft", provider="deterministic_evidence_builder",
        model="resume-evidence-v1",
    )
    db.add(artifact)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="resume.cover_letter_drafted",
                    resource_type="generated_artifact", resource_id=str(artifact.id),
                    metadata_json={"resume_id": resume.id,
                                   "opportunity_id": opportunity.id if opportunity else None}))
    db.commit()
    db.refresh(artifact)
    return {"id": artifact.id, "artifact_type": artifact.artifact_type,
            "title": artifact.title, "content": artifact.content,
            "status": artifact.status, "evidence_sentences": draft["evidence_sentences"],
            "claims_invented": False, "requires_candidate_review": True}


class TailoredArtifactRequest(BaseModel):
    job_description: str = Field(min_length=20, max_length=30000)
    role_title: str = Field(min_length=2, max_length=250)
    opportunity_id: int | None = None
    parent_artifact_id: int | None = None

@router.post("/{resume_id}/tailored-artifacts", status_code=201)
def create_tailored_artifact(resume_id: int, body: TailoredArtifactRequest,
                             user: User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """Create a versioned, reviewable resume variant without modifying its source."""
    enforce_rate_limit(f"resume-version:{user.id}", limit=15, window_seconds=3600)
    resume = db.scalar(select(ResumeDocument).where(
        ResumeDocument.id == resume_id, ResumeDocument.user_id == user.id))
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    opportunity = None
    if body.opportunity_id is not None:
        opportunity = db.scalar(select(CandidateOpportunity).where(
            CandidateOpportunity.id == body.opportunity_id,
            CandidateOpportunity.user_id == user.id))
        if not opportunity:
            raise HTTPException(status_code=404, detail="Opportunity not found")
    parent = None
    if body.parent_artifact_id is not None:
        parent = db.scalar(select(GeneratedArtifact).where(
            GeneratedArtifact.id == body.parent_artifact_id,
            GeneratedArtifact.user_id == user.id,
            GeneratedArtifact.artifact_type == "tailored_resume"))
        if not parent:
            raise HTTPException(status_code=404, detail="Parent tailored artifact not found")
    try:
        proposal = tailor_resume(resume.extracted_text, body.job_description)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not proposal["items"]:
        raise HTTPException(status_code=422, detail="No source resume evidence matches this role")
    source_hash = hashlib.sha256(resume.extracted_text.encode()).hexdigest()
    job_hash = hashlib.sha256(body.job_description.encode()).hexdigest()
    previous = db.scalar(select(GeneratedArtifact).where(
        GeneratedArtifact.user_id == user.id,
        GeneratedArtifact.artifact_type == "tailored_resume",
        GeneratedArtifact.source_resume_id == resume.id,
        GeneratedArtifact.job_description_sha256 == job_hash,
    ).order_by(GeneratedArtifact.version_number.desc()).limit(1))
    version = (previous.version_number + 1) if previous else 1
    content = "\n\n".join(
        [f"# {body.role_title} | Tailored resume draft",
         "Candidate-reviewed relevance ordering of existing resume evidence.",
         *[f"- {item['text']}" for item in proposal["items"]]]
    )
    artifact = GeneratedArtifact(
        user_id=user.id, artifact_type="tailored_resume",
        title=f"{body.role_title} resume v{version}", content=content,
        source_resume_id=resume.id,
        source_opportunity_id=opportunity.id if opportunity else None,
        status="draft", provider="evidence_preserving_tailoring",
        model="resume-ranker-v2", version_number=version,
        source_sha256=source_hash, job_description_sha256=job_hash,
        parent_artifact_id=parent.id if parent else None,
    )
    db.add(artifact)
    db.flush()
    db.add(AuditLog(user_id=user.id, action="resume.tailored_version_created",
                    resource_type="generated_artifact", resource_id=str(artifact.id),
                    metadata_json={"resume_id": resume.id, "version": version,
                                   "source_sha256": source_hash, "job_sha256": job_hash}))
    db.commit()
    db.refresh(artifact)
    return {"id": artifact.id, "title": artifact.title, "version": artifact.version_number,
            "status": artifact.status, "content": artifact.content,
            "matched_terms": proposal["matched_terms"],
            "unmatched_job_terms": proposal["unmatched_job_terms"],
            "source_sha256": source_hash, "job_description_sha256": job_hash,
            "claims_invented": False, "requires_candidate_review": True}

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
