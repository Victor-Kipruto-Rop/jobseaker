"""Evidence-first email intent classification; never mutates application state."""
from __future__ import annotations
import re
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class EmailIntent:
    intent: str
    confidence: float
    evidence: tuple[str, ...]
    requires_review: bool = True

_RULES = (
    ("offer", (r"\b(offer of employment|pleased to offer|employment offer)\b",), 0.96),
    ("rejection", (r"\b(unfortunately|not moving forward|decided not to proceed|regret to inform)\b",), 0.88),
    ("interview", (r"\b(interview|schedule a call|availability for a call|meet the team)\b",), 0.90),
    ("assessment", (r"\b(assessment|coding challenge|take[- ]home exercise|technical test)\b",), 0.90),
    ("screening", (r"\b(recruiter screen|phone screen|initial screening|screening call)\b",), 0.88),
    ("application_confirmation", (r"\b(application received|thank you for applying|we received your application)\b",), 0.94),
)

def classify_email(subject: str, body: str) -> dict:
    """Classify bounded text and return matched phrases as auditable evidence."""
    text = re.sub(r"\s+", " ", f"{subject or ''} {body or ''}".casefold())[:30000]
    matches = []
    for intent, patterns, confidence in _RULES:
        evidence = tuple(sorted({m.group(0) for pattern in patterns for m in re.finditer(pattern, text)}))
        if evidence:
            matches.append(EmailIntent(intent, confidence, evidence))
    if not matches:
        result = EmailIntent("unknown", 0.0, ())
    else:
        matches.sort(key=lambda item: (item.confidence, len(item.evidence)), reverse=True)
        winner = matches[0]
        # Conflicting high-signal outcomes must be reviewed as ambiguous.
        if len(matches) > 1 and matches[1].confidence >= winner.confidence - 0.08:
            result = EmailIntent("ambiguous", 0.5, tuple(
                f"{item.intent}:{phrase}" for item in matches[:3] for phrase in item.evidence
            ))
        else:
            result = winner
    return asdict(result) | {"evidence": list(result.evidence), "source": "subject_and_body",
                             "state_change_permitted": False}
