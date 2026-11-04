"""Single source of truth for candidate application lifecycle transitions."""
from __future__ import annotations

STATUSES = {
    "draft", "ready", "approved", "submitted", "screening", "interview",
    "assessment", "offer", "accepted", "rejected", "withdrawn", "archived",
}

TRANSITIONS = {
    "draft": {"ready", "withdrawn", "archived"},
    "ready": {"draft", "withdrawn", "archived"},
    "approved": {"ready", "submitted", "withdrawn"},
    "submitted": {"screening", "interview", "assessment", "rejected", "withdrawn"},
    "screening": {"interview", "assessment", "rejected", "withdrawn"},
    "interview": {"assessment", "offer", "rejected", "withdrawn"},
    "assessment": {"interview", "offer", "rejected", "withdrawn"},
    "offer": {"accepted", "rejected", "withdrawn"},
    "accepted": {"archived"},
    "rejected": {"archived"},
    "withdrawn": {"archived"},
    "archived": set(),
}


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())
