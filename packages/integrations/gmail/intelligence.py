"""Evidence-backed recruiter email intent extraction; never mutates application state."""
from __future__ import annotations
import re
from typing import Iterable, Any

INTENTS = {
    "interview_invitation": ("interview", "schedule a call", "availability for a call", "meet with"),
    "assessment_request": ("assessment", "technical test", "coding test", "take-home"),
    "rejection": ("unfortunately", "not be moving forward", "not selected", "regret to inform"),
    "offer_or_salary": ("offer letter", "salary expectation", "compensation package", "pleased to offer"),
    "information_request": ("please provide", "could you share", "additional information"),
    "acknowledgement": ("application received", "thank you for applying", "we have received"),
}
SUGGESTED_STATES = {
    "interview_invitation": "interview",
    "assessment_request": "assessment",
    "rejection": "rejected",
    "offer_or_salary": "offer",
}


def _norm(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").lower()))


def analyze_recruiter_email(
    subject: str, body: str, applications: Iterable[Any],
) -> dict:
    """Classify minimal email text and link only when one application is unambiguous."""
    text = f"{subject or ''}\n{body or ''}"[:20000]
    lowered = text.lower()
    intent = "unclassified"
    evidence = []
    confidence = 0.15
    for label, phrases in INTENTS.items():
        hits = [phrase for phrase in phrases if phrase in lowered]
        if hits:
            intent = label
            evidence.extend(hits[:3])
            confidence = min(0.92, 0.62 + 0.10 * len(hits))
            break

    matches = []
    normalized_text = _norm(text)
    for application in applications:
        role = _norm(getattr(application, "role_title", ""))
        company = _norm(getattr(application, "company_name", ""))
        role_hit = bool(role and len(role) >= 5 and role in normalized_text)
        company_hit = bool(company and len(company) >= 3 and company in normalized_text)
        score = int(role_hit) + int(company_hit)
        if score:
            matches.append((score, application.id, role_hit, company_hit))
    matches.sort(reverse=True)
    application_id = None
    if matches and (len(matches) == 1 or matches[0][0] > matches[1][0]):
        application_id = matches[0][1]
        confidence = min(0.98, confidence + (0.12 if matches[0][0] == 2 else 0.05))
        evidence.append("matched_application_role" if matches[0][2] else "matched_application_company")
    elif matches:
        evidence.append("ambiguous_application_match")

    interview_text = ""
    if intent == "interview_invitation":
        date_patterns = (
            r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?[,]?\s+\d{1,2}\s+"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b",
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
            r"\d{1,2}(?:st|nd|rd|th)?[,]?\s+\d{4}\b",
            r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?:\s?[A-Z]{2,5}|Z|[+-]\d{2}:?\d{2})?)?\b",
        )
        for pattern in date_patterns:
            found = re.search(pattern, text, flags=re.IGNORECASE)
            if found:
                interview_text = found.group(0)[:500]
                evidence.append("interview_time_text_extracted")
                break

    return {
        "intent": intent,
        "suggested_status": SUGGESTED_STATES.get(intent, ""),
        "confidence": round(confidence, 3),
        "application_id": application_id,
        "interview_proposed_text": interview_text,
        "evidence": {"matched_phrases": evidence, "source": "email_subject_and_body",
                     "state_change_requires_candidate_confirmation": True},
        "action_required": intent in {
            "interview_invitation", "assessment_request", "offer_or_salary", "information_request",
        },
    }
