import csv
import hashlib
import io
from pathlib import Path
from dataclasses import dataclass, asdict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SourceImportRow


ALIASES = {
    "message_id": ("gmail_message_id", "message_id", "gmail_id", "gmail_api_message_id"),
    "thread_id": ("gmail_thread_id", "thread_id", "gmail_thread", "gmail_api_thread_id"),
    "organization": ("organization", "company", "company_name", "employer"),
    "recipient": ("recipient", "to", "email", "recipient_email"),
    "status": ("status", "send_status", "outreach_status"),
}


@dataclass
class SendLogReport:
    total_rows: int = 0
    inserted: int = 0
    already_imported: int = 0
    rows_with_message_id: int = 0
    rows_with_thread_id: int = 0
    rows_without_message_id: int = 0
    errors: list | None = None

    def as_dict(self):
        return asdict(self)


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("Unsupported CSV encoding; export the file as UTF-8.")


def parse_send_log(content: bytes):
    text = _decode(content)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("Send log CSV has no header.")
    result = []
    for raw in reader:
        payload = {str(k or "").strip(): (v.strip() if isinstance(v, str) else v)
                   for k, v in raw.items()}
        normalized = {}
        for target, aliases in ALIASES.items():
            normalized[target] = next((payload[a] for a in aliases if a in payload and payload[a]), None)
        result.append((payload, normalized))
    return result


def import_send_log(db: Session, content: bytes, filename: str, *, dry_run: bool = False) -> SendLogReport:
    rows = parse_send_log(content)
    file_hash = hashlib.sha256(Path(filename).name.strip().lower().encode("utf-8")).hexdigest()
    report = SendLogReport(total_rows=len(rows), errors=[])
    for index, (payload, normalized) in enumerate(rows, start=2):
        row_hash = hashlib.sha256(
            (str(index) + "\\x1f" + repr(sorted(payload.items()))).encode("utf-8")
        ).hexdigest()
        report.rows_with_message_id += bool(normalized["message_id"])
        report.rows_with_thread_id += bool(normalized["thread_id"])
        report.rows_without_message_id += not bool(normalized["message_id"])
        exists = db.scalar(select(SourceImportRow.id).where(
            SourceImportRow.source_file_key == file_hash,
            SourceImportRow.row_key == row_hash
        ))
        if exists:
            report.already_imported += 1
            continue
        if not dry_run:
            db.add(SourceImportRow(
                source_file_key=file_hash,
                source_filename=filename,
                row_key=row_hash,
                gmail_message_id=normalized["message_id"],
                gmail_thread_id=normalized["thread_id"],
                organization=normalized["organization"],
                recipient=normalized["recipient"],
                status=normalized["status"],
                original_payload=payload,
            ))
            report.inserted += 1
    if not dry_run:
        db.commit()
    return report
