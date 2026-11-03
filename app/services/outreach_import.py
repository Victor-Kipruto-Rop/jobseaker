import csv
import hashlib
import io
from dataclasses import dataclass, asdict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OutreachContact


FIELD_ALIASES = {
    "organization": ("organization", "company", "company_name"),
    "sector": ("sector", "industry"),
    "email": ("email", "contact_email"),
    "contact_type": ("contact_type", "email_type"),
    "website": ("website", "company_website"),
    "source_url": ("source_url", "source"),
    "contact_verification": ("contact_verification", "verification"),
    "contact_notes": ("contact_notes", "notes"),
    "outreach_status": ("outreach_status", "status"),
    "cv_attached": ("cv_attached", "resume_attached"),
    "date_contacted": ("date_contacted", "sent_date"),
    "follow_up_date": ("follow_up_date",),
    "response": ("response", "reply"),
    "next_action": ("next_action",),
}


@dataclass
class ImportReport:
    total_rows: int = 0
    valid_rows: int = 0
    inserted: int = 0
    already_imported: int = 0
    invalid_rows: int = 0
    errors: list | None = None

    def as_dict(self):
        return asdict(self)


def _decode_csv(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV encoding is not supported. Save it as UTF-8 and retry.")


def parse_csv(content: bytes) -> tuple[list[dict], list[str]]:
    text = _decode_csv(content)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")
    headers = [str(h or "").strip() for h in reader.fieldnames]
    rows = []
    for raw in reader:
        normalized = {str(k or "").strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
        record = {}
        for field, aliases in FIELD_ALIASES.items():
            match = next((normalized[a] for a in aliases if a in normalized), None)
            record[field] = match or None
        record["original_payload"] = normalized
        rows.append(record)
    return rows, headers


def _source_key(payload: dict) -> str:
    canonical = "\x1f".join(f"{k}={payload.get(k, '') or ''}" for k in sorted(payload))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def import_outreach_csv(db: Session, content: bytes, *, dry_run: bool = False) -> ImportReport:
    rows, _ = parse_csv(content)
    report = ImportReport(total_rows=len(rows), errors=[])
    seen_in_file = set()

    for row_number, row in enumerate(rows, start=2):
        payload = row["original_payload"]
        if not row.get("organization"):
            report.invalid_rows += 1
            report.errors.append({"row": row_number, "error": "Missing organization/company"})
            continue

        key = _source_key(payload)
        report.valid_rows += 1
        if key in seen_in_file or db.scalar(select(OutreachContact.id).where(OutreachContact.source_key == key)):
            report.already_imported += 1
            seen_in_file.add(key)
            continue
        seen_in_file.add(key)
        if not dry_run:
            db.add(OutreachContact(source_key=key, **{k: v for k, v in row.items() if k != "original_payload"},
                                   original_payload=payload))
            report.inserted += 1

    if not dry_run:
        db.commit()
    return report
