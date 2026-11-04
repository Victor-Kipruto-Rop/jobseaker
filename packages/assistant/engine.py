"""Privacy-aware memory, hybrid retrieval, context assembly and safe tool planning.

The baseline works without optional ML dependencies. Sentence-transformer embeddings
and cross-encoder reranking are opportunistic; lexical retrieval remains deterministic.
"""
from __future__ import annotations
import hashlib, math, re
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.database.models.assistant import AssistantMemory, AssistantFact, AssistantPreference

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]{1,40}")
PII_PATTERNS = [
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL_REDACTED]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)"), "[PHONE_REDACTED]"),
    (re.compile(r"\b\d{8,}\b"), "[LONG_NUMBER_REDACTED]"),
]
FACT_PATTERNS = [
    ("career_goal", re.compile(r"(?i)\b(?:my goal is|I want to become|I am targeting)\s+([^.!?\n]{3,140})")),
    ("preferred_role", re.compile(r"(?i)\b(?:I prefer|I am interested in|I specialize in)\s+([^.!?\n]{3,140})")),
    ("technical_preference", re.compile(r"(?i)\b(?:I use|my stack is|I prefer using)\s+([^.!?\n]{3,140})")),
    ("communication_preference", re.compile(r"(?i)\b(?:keep it|make it|write it)\s+(concise|detailed|technical|simple|professional)\b")),
]

def sanitize(text: str) -> str:
    value = text or ""
    for pattern, replacement in PII_PATTERNS:
        value = pattern.sub(replacement, value)
    return value[:30000]

def tokens(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text or "")]

def embedding(text: str, dimensions: int = 96) -> list[float]:
    """Deterministic feature-hash embedding; replaceable by configured transformer provider."""
    vector = [0.0] * dimensions
    terms = tokens(text)
    for term in terms:
        digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(x*x for x in vector)) or 1.0
    return [round(x / norm, 6) for x in vector]

def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b): return 0.0
    return max(0.0, sum(x*y for x,y in zip(a,b)))

def bm25_score(query: str, document: str) -> float:
    q = tokens(query); d = tokens(document)
    if not q or not d: return 0.0
    counts = Counter(d); length = len(d)
    score = sum((counts[t] * 2.2) / (counts[t] + 1.2 * (0.25 + 0.75 * length / 180)) for t in set(q))
    return score / max(len(set(q)), 1)

def semantic_chunks(text: str, max_chars: int = 1400) -> list[str]:
    """Split by markdown headings, paragraphs and code fences before size fallback."""
    source = (text or "").strip()
    if not source: return []
    blocks = re.split(r"(?=^#{1,6}\s)|\n\s*\n", source, flags=re.M)
    chunks: list[str] = []; current = ""
    for block in blocks:
        block = block.strip()
        if not block: continue
        if len(block) > max_chars:
            pieces = re.split(r"(?<=\.)\s+", block)
        else: pieces = [block]
        for piece in pieces:
            if current and len(current) + len(piece) + 2 > max_chars:
                chunks.append(current); current = ""
            current = (current + "\n\n" + piece).strip()
    if current: chunks.append(current)
    return chunks

def extract_facts(text: str) -> list[tuple[str, str, float]]:
    clean = sanitize(text); facts = []
    for key, pattern in FACT_PATTERNS:
        for match in pattern.finditer(clean):
            value = match.group(1).strip(" .,:;")
            if value and len(value) >= 3:
                facts.append((key, value[:500], 0.68))
    return facts[:8]

def remember(db: Session, user_id: int, content: str, conversation_id: int | None = None,
             source: str = "conversation") -> int | None:
    clean = sanitize(content)
    if len(clean.strip()) < 20: return None
    chunks = semantic_chunks(clean)
    first_id = None
    for chunk in chunks[:12]:
        row = AssistantMemory(user_id=user_id, conversation_id=conversation_id,
            memory_kind="episodic", content=chunk, summary=chunk[:500],
            embedding=embedding(chunk), keywords=list(dict.fromkeys(tokens(chunk)))[:40],
            importance=0.55, source=source)
        db.add(row); db.flush()
        first_id = first_id or row.id
        for key, value, confidence in extract_facts(chunk):
            fact = db.scalar(select(AssistantFact).where(
                AssistantFact.user_id == user_id, AssistantFact.fact_key == key))
            if fact is None:
                db.add(AssistantFact(user_id=user_id, fact_key=key, fact_value=value,
                    confidence=confidence, source_memory_id=row.id))
            elif not fact.verified_by_user:
                fact.fact_value = value; fact.confidence = confidence; fact.source_memory_id = row.id
    return first_id

def retrieve(db: Session, user_id: int, query: str, limit: int = 8) -> list[dict[str, Any]]:
    qvec = embedding(query)
    rows = db.scalars(select(AssistantMemory).where(
        AssistantMemory.user_id == user_id).order_by(AssistantMemory.created_at.desc()).limit(600)).all()
    ranked = []
    for row in rows:
        dense = cosine(qvec, row.embedding or [])
        sparse = bm25_score(query, row.content)
        score = 0.58 * dense + 0.42 * min(sparse, 1.0)
        ranked.append((score, row))
    ranked.sort(key=lambda x: (x[0], x[1].importance), reverse=True)
    return [{"id": row.id, "content": row.summary or row.content,
             "score": round(score, 4), "kind": row.memory_kind}
            for score, row in ranked[:limit] if score > 0.015]

def preference_snapshot(db: Session, user_id: int) -> dict:
    row = db.scalar(select(AssistantPreference).where(AssistantPreference.user_id == user_id))
    return row.preferences if row else {}

def build_context(db: Session, user_id: int, query: str, history: list[dict],
                  budget_chars: int = 12000) -> str:
    facts = db.scalars(select(AssistantFact).where(
        AssistantFact.user_id == user_id, AssistantFact.active.is_(True)).limit(40)).all()
    memories = retrieve(db, user_id, query, limit=8)
    prefs = preference_snapshot(db, user_id)
    sections = ["USER FACTS (unverified unless explicitly marked):"]
    sections.extend(f"- {f.fact_key}: {f.fact_value} (confidence {f.confidence:.2f}; verified={f.verified_by_user})" for f in facts)
    sections.append("RELEVANT EPISODIC MEMORY:")
    sections.extend(f"- {m['content']}" for m in memories)
    sections.append("PREFERENCES:")
    sections.append(str(prefs)[:2000])
    sections.append("RECENT CONVERSATION:")
    sections.extend(f"{m.get('role','user')}: {sanitize(m.get('content',''))[:1800]}" for m in history[-8:])
    return "\n".join(sections)[:budget_chars]

def plan_tools(query: str) -> list[str]:
    """Only read-only internal tools are eligible for automatic invocation."""
    q = query.lower()
    tools = []
    if any(x in q for x in ("my applications", "application status", "applications")): tools.append("application_summary")
    if any(x in q for x in ("my interviews", "upcoming interview", "interview schedule")): tools.append("interview_summary")
    if any(x in q for x in ("my skills", "my profile", "my resume", "my cv")): tools.append("candidate_profile")
    if any(x in q for x in ("recommend jobs", "job recommendations", "jobs for me")): tools.append("job_recommendations")
    return tools

def adapt_preferences(current: dict, rating: int, correction: str) -> dict:
    result = dict(current)
    result["feedback_events"] = int(result.get("feedback_events", 0)) + 1
    if rating <= 2 and correction.strip():
        result["correction_patterns"] = (result.get("correction_patterns", []) + [sanitize(correction)[:300]])[-20:]
    elif rating >= 4:
        result["successful_response_count"] = int(result.get("successful_response_count", 0)) + 1
    return result
