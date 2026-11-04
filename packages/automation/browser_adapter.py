"""Guarded Playwright adapter for individually approved ATS field fills.

This adapter never clicks submit, never navigates to a new origin, and requires
an externally persisted approval plus an idempotency store for every action.
"""
from __future__ import annotations
import hashlib
import hmac
import json
from typing import Protocol

class ActionStore(Protocol):
    def claim(self, action_id: str, payload_hash: str) -> bool: ...
    def complete(self, action_id: str, evidence: dict) -> None: ...
    def fail(self, action_id: str, reason: str) -> None: ...

def action_digest(application_id: int, draft_hash: str, field_id: str,
                  label: str, value: str) -> str:
    payload = [application_id, draft_hash, field_id, label, value]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False,
        separators=(",", ":")).encode()).hexdigest()

async def execute_approved_fill(page, *, application_id: int, draft_hash: str,
                                field_id: str, label: str, value: str,
                                approved_digest: str, approved_origin: str,
                                action_store: ActionStore) -> dict:
    """Fill one exact label only after matching the candidate-approved digest."""
    if not label.strip() or len(label) > 200 or not field_id.strip() or len(field_id) > 200:
        raise ValueError("A bounded, exact field label and identifier are required")
    expected = action_digest(application_id, draft_hash, field_id, label, value)
    if not approved_digest or not hmac.compare_digest(expected, approved_digest):
        raise PermissionError("Candidate approval does not match this exact field action")
    assert_safe_target(str(page.url), approved_origin)
    action_id = hashlib.sha256(f"{application_id}:{draft_hash}:{field_id}".encode()).hexdigest()
    if not action_store.claim(action_id, expected):
        return {"status": "already_claimed_or_completed", "action_id": action_id}
    try:
        locator = page.get_by_label(label, exact=True)
        count = await locator.count()
        if count != 1:
            raise RuntimeError("ATS label did not resolve to exactly one form control")
        await locator.fill(value)
        observed = await locator.input_value()
        if observed != value:
            raise RuntimeError("ATS field value did not match the approved value after fill")
        screenshot = await page.screenshot(full_page=False)
        evidence = {
            "action_id": action_id, "field_id": field_id, "label": label,
            "approved_digest": expected, "observed_value_sha256": hashlib.sha256(
                observed.encode()).hexdigest(),
            "screenshot_sha256": hashlib.sha256(screenshot).hexdigest(),
            "action": "fill", "verified": True,
        }
        action_store.complete(action_id, evidence)
        return {"status": "completed", "action_id": action_id, "evidence": evidence}
    except Exception as exc:
        action_store.fail(action_id, str(exc)[:500])
        raise

def assert_safe_target(current_url: str, approved_origin: str) -> None:
    from urllib.parse import urlsplit
    current, approved = urlsplit(current_url), urlsplit(approved_origin)
    if (current.scheme != "https" or approved.scheme != "https"
            or current.hostname != approved.hostname
            or current.port != approved.port):
        raise PermissionError("Browser target left the candidate-approved HTTPS origin")
