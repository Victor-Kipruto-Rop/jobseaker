"""Candidate-reviewed mapping for common ATS fields; never submits a form."""
from dataclasses import asdict, dataclass
import hashlib
import json
ALIASES = {
 "first_name": ("first name", "given name"), "last_name": ("last name", "surname"),
 "full_name": ("full name",), "email": ("email", "email address"),
 "phone": ("phone", "mobile", "telephone"), "location": ("location", "city"),
 "linkedin_url": ("linkedin", "linkedin url"), "portfolio_url": ("portfolio", "website"),
 "resume_url": ("resume", "cv"), "cover_letter": ("cover letter",),
}
@dataclass(frozen=True)
class FieldMapping:
 field_id: str
 label: str
 key: str | None
 value: str | None
 status: str
 reason: str
def resolve_field(label: str) -> str | None:
 value = " ".join((label or "").casefold().replace("_", " ").split())
 found = [key for key, aliases in ALIASES.items() if value == key.replace("_", " ") or value in aliases]
 return found[0] if len(found) == 1 else None
def build_mapping(fields: list[dict], candidate: dict) -> list[FieldMapping]:
 seen, result = set(), []
 for field in fields[:250]:
  field_id, label = str(field.get("id") or "").strip(), str(field.get("label") or "")[:200]
  if not field_id or field_id in seen:
   result.append(FieldMapping(field_id, label, None, None, "blocked", "invalid_field_id")); continue
  seen.add(field_id); key = resolve_field(label)
  if key is None:
   result.append(FieldMapping(field_id, label, None, None, "needs_review", "unknown_label")); continue
  value = str(candidate.get(key) or "").strip()
  result.append(FieldMapping(field_id, label, key, value or None,
   "proposed" if value else "needs_input", "allowlisted_exact_match" if value else "candidate_value_missing"))
 return result
def approval_manifest(application_id: int, mappings: list[FieldMapping], confirmed: bool) -> dict:
 rows = [asdict(row) for row in mappings]
 digest = hashlib.sha256(json.dumps([application_id, rows], sort_keys=True).encode()).hexdigest()
 return {"application_id": application_id, "mapping_sha256": digest,
  "candidate_confirmed": bool(confirmed),
  "approved": bool(confirmed) and bool(rows) and all(row.status == "proposed" for row in mappings),
  "mappings": rows, "execution_policy": "candidate_review_required"}
