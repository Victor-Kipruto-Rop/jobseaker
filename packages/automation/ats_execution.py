"""Database-backed executor for candidate-approved ATS field actions."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.database.models.career import ATSActionApproval, ATSApplicationDraft, Application
from packages.security.credential_vault import decrypt_credential
from packages.automation.browser_adapter import execute_approved_fill, action_digest

class DatabaseActionStore:
    def __init__(self, db: Session, approval: ATSActionApproval):
        self.db, self.approval = db, approval

    def claim(self, action_id: str, payload_hash: str) -> bool:
        row = self.db.scalar(select(ATSActionApproval).where(
            ATSActionApproval.id == self.approval.id).with_for_update())
        if row is None or row.action_digest != payload_hash:
            raise PermissionError("Persisted ATS approval does not match this action")
        if row.status == "completed" or row.status == "executing":
            return False
        if row.status != "approved" and row.status != "failed":
            raise PermissionError("ATS field action is not approved for execution")
        row.status = "executing"
        row.last_error = ""
        self.db.commit()
        return True

    def complete(self, action_id: str, evidence: dict) -> None:
        row = self.db.get(ATSActionApproval, self.approval.id)
        row.status = "completed"
        row.executed_at = datetime.now(timezone.utc)
        row.evidence = evidence
        self.db.commit()

    def fail(self, action_id: str, reason: str) -> None:
        row = self.db.get(ATSActionApproval, self.approval.id)
        row.status = "failed"
        row.last_error = reason[:500]
        self.db.commit()

async def execute_ats_field(db: Session, page, *, user_id: int,
                            application_id: int, field_id: str,
                            approved_origin: str) -> dict:
    """Execute one already-approved fill. The caller owns the authenticated browser session."""
    approval = db.scalar(select(ATSActionApproval).where(
        ATSActionApproval.user_id == user_id,
        ATSActionApproval.application_id == application_id,
        ATSActionApproval.field_id == field_id).with_for_update())
    if approval is None:
        raise PermissionError("No candidate approval exists for this ATS field")
    if approval.status == "completed":
        return {"status": "completed", "idempotent": True,
                "evidence": approval.evidence or {}}
    draft = db.scalar(select(ATSApplicationDraft).where(
        ATSApplicationDraft.id == approval.draft_id,
        ATSApplicationDraft.user_id == user_id,
        ATSApplicationDraft.application_id == application_id))
    application = db.scalar(select(Application).where(
        Application.id == application_id, Application.user_id == user_id))
    if not draft or not application or not draft.candidate_confirmed:
        raise PermissionError("ATS draft or application ownership could not be verified")
    mapping = next((dict(item) for item in (draft.mappings or [])
                    if str(item.get("field_id")) == field_id), None)
    if not mapping or mapping.get("status") != "proposed":
        raise PermissionError("Approved field mapping is no longer available")
    token = mapping.get("value_ciphertext")
    if not token:
        raise PermissionError("Encrypted ATS field value is missing")
    value = decrypt_credential(token, purpose="ats-field-value")
    digest = action_digest(application_id, draft.mapping_sha256, field_id,
                           str(mapping.get("label") or ""), value)
    if digest != approval.action_digest:
        raise PermissionError("ATS field value or draft changed after candidate approval")
    return await execute_approved_fill(
        page, application_id=application_id, draft_hash=draft.mapping_sha256,
        field_id=field_id, label=str(mapping.get("label") or ""), value=value,
        approved_digest=approval.action_digest, approved_origin=approved_origin,
        evidence_owner_scope=str(user_id), action_store=DatabaseActionStore(db, approval),
    )
