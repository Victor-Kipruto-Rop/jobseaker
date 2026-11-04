"""Privacy-aware memory, hybrid retrieval, context assembly and safe tool planning.

The baseline works without optional ML dependencies. Sentence-transformer embeddings
and cross-encoder reranking are opportunistic; lexical retrieval remains deterministic.
"""
from __future__ import annotations
import hashlib, math, re, os, json
from functools import lru_cache
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from packages.database.models.assistant import AssistantMemory, AssistantFact, AssistantPreference, AssistantEntity, AssistantRelation
from packages.assistant.entity_resolution import index_entities
from packages.security.credential_vault import encrypt_credential, decrypt_credential

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]{1,40}")
PII_PATTERNS = [
    (re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+"), r"\1=[REDACTED]"),
    (re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b"), "[TOKEN_REDACTED]"),
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{20,}"), "Bearer [TOKEN_REDACTED]"),
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

@lru_cache(maxsize=1)
def _sentence_model():
    model_name = os.getenv("JOBSEEKER_MEMORY_EMBEDDING_MODEL", "").strip()
    if not model_name:
        return None
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer(model_name)
    except Exception:
        return None

@lru_cache(maxsize=1)
def _cross_encoder():
    model_name = os.getenv("JOBSEEKER_CROSS_ENCODER_MODEL", "").strip()
    if not model_name:
        return None
    try:
        from sentence_transformers import CrossEncoder
        return CrossEncoder(model_name)
    except Exception:
        return None

def embedding(text: str, dimensions: int = 384) -> list[float]:
    """Configured transformer embeddings with deterministic offline fallback."""
    model = _sentence_model()
    if model is not None:
        try:
            values = model.encode([text], normalize_embeddings=True)[0].tolist()
            return [round(float(x), 6) for x in (list(values[:dimensions]) + [0.0] * max(0, dimensions - len(values)))]
        except Exception:
            pass
    vector = [0.0] * dimensions
    for term in tokens(text):
        digest = hashlib.blake2b(term.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1.0 if digest[4] & 1 else -1.0
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
        if block.startswith("#") and current:
            chunks.append(current)
            current = ""
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


def extractive_summary(text: str, max_chars: int = 500) -> str:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
    if not sentences:
        return (text or "")[:max_chars]
    frequencies = Counter(tokens(text))
    ranked = sorted(enumerate(sentences), key=lambda item: (
        sum(frequencies[t] for t in set(tokens(item[1]))) / max(len(tokens(item[1])), 1),
        -item[0]), reverse=True)
    selected = sorted([sentence for _, sentence in ranked[:3]], key=lambda s: sentences.index(s))
    return " ".join(selected)[:max_chars]

def _upsert_graph_fact(db: Session, user_id: int, key: str, value: str, memory_id: int) -> None:
    mapping = {
        "career_goal": ("goal", "has_goal"),
        "preferred_role": ("role", "targets_role"),
        "technical_preference": ("technology", "uses_technology"),
        "communication_preference": ("preference", "prefers_style"),
    }
    kind, relation = mapping.get(key, ("fact", "has_fact"))
    normalized = re.sub(r"\s+", " ", value.strip().lower())[:240]
    if not normalized:
        return
    candidate = db.scalar(select(AssistantEntity).where(
        AssistantEntity.user_id == user_id, AssistantEntity.entity_type == "candidate",
        AssistantEntity.normalized_name == "candidate"))
    if candidate is None:
        candidate = AssistantEntity(user_id=user_id, entity_type="candidate",
            name="Candidate", normalized_name="candidate", attributes={})
        db.add(candidate)
        db.flush()
    entity = db.scalar(select(AssistantEntity).where(
        AssistantEntity.user_id == user_id, AssistantEntity.entity_type == kind,
        AssistantEntity.normalized_name == normalized))
    if entity is None:
        entity = AssistantEntity(user_id=user_id, entity_type=kind, name=value[:240],
            normalized_name=normalized, attributes={}, source_memory_id=memory_id)
        db.add(entity)
        db.flush()
    edge = db.scalar(select(AssistantRelation).where(
        AssistantRelation.user_id == user_id,
        AssistantRelation.source_entity_id == candidate.id,
        AssistantRelation.target_entity_id == entity.id,
        AssistantRelation.relation_type == relation))
    if edge is None:
        db.add(AssistantRelation(user_id=user_id, source_entity_id=candidate.id,
            target_entity_id=entity.id, relation_type=relation, confidence=0.68))

def remember(db: Session, user_id: int, content: str, conversation_id: int | None = None,
             source: str = "conversation") -> int | None:
    clean = sanitize(content)
    if len(clean.strip()) < 20: return None
    chunks = semantic_chunks(clean)
    first_id = None
    preference = db.scalar(select(AssistantPreference).where(AssistantPreference.user_id == user_id))
    retention_days = max(30, min(730, int(preference.memory_retention_days if preference else 365)))
    postgres_index = db.get_bind().dialect.name == "postgresql"
    for chunk in chunks[:80]:
        vector = embedding(chunk)
        row = AssistantMemory(user_id=user_id, conversation_id=conversation_id,
            memory_kind="episodic",
            content=encrypt_credential(chunk, purpose=f"assistant-memory:{user_id}"),
            summary=encrypt_credential(extractive_summary(chunk), purpose=f"assistant-memory:{user_id}"),
            content_encrypted=True, embedding=[] if postgres_index else vector,
            embedding_vector=vector, expires_at=datetime.now(timezone.utc) + timedelta(days=retention_days),
            keywords=[],
            importance=0.25 if source == "assistant_response" else 0.55, source=source)
        db.add(row); db.flush()
        first_id = first_id or row.id
        if source in {"conversation", "document"}:
            index_entities(db, user_id, chunk, row.id)
        for key, value, confidence in (extract_facts(chunk) if source in {"conversation", "document"} else []):
            fact = db.scalar(select(AssistantFact).where(
                AssistantFact.user_id == user_id, AssistantFact.fact_key == key))
            if fact is None:
                db.add(AssistantFact(user_id=user_id, fact_key=key, fact_value=encrypt_credential(value, purpose=f"assistant-fact:{user_id}"),
                    fact_value_encrypted=True, confidence=confidence, source_memory_id=row.id))
            elif not fact.verified_by_user:
                fact.fact_value = encrypt_credential(value, purpose=f"assistant-fact:{user_id}"); fact.fact_value_encrypted = True; fact.confidence = confidence; fact.source_memory_id = row.id
            _upsert_graph_fact(db, user_id, key, value, row.id)
    return first_id

def preference_snapshot(db: Session, user_id: int) -> dict:
    row = db.scalar(select(AssistantPreference).where(AssistantPreference.user_id == user_id))
    if row is None:
        return {}
    if row.preference_vector:
        row.preference_vector = []
    if row.preferences_encrypted and isinstance(row.preferences, str):
        try:
            value = json.loads(decrypt_credential(row.preferences, purpose=f"assistant-preferences:{user_id}"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
    value = row.preferences if isinstance(row.preferences, dict) else {}
    if value:
        row.preferences = encrypt_credential(json.dumps(value, separators=(",", ":"), ensure_ascii=False),
                                             purpose=f"assistant-preferences:{user_id}")
        row.preferences_encrypted = True
        row.preference_vector = []
    return value

def store_preferences(db: Session, user_id: int, value: dict) -> AssistantPreference:
    row = db.scalar(select(AssistantPreference).where(AssistantPreference.user_id == user_id))
    if row is None:
        row = AssistantPreference(user_id=user_id)
        db.add(row)
    serialized = json.dumps(value or {}, separators=(",", ":"), ensure_ascii=False)
    row.preferences = encrypt_credential(serialized, purpose=f"assistant-preferences:{user_id}")
    row.preferences_encrypted = True
    row.preference_vector = []
    return row

def adapt_preferences(current: dict, rating: int, correction: str) -> dict:
    result = dict(current or {})
    result["feedback_events"] = int(result.get("feedback_events", 0)) + 1
    if rating <= 2 and correction.strip():
        result["correction_patterns"] = (result.get("correction_patterns", []) + [sanitize(correction)[:300]])[-20:]
    elif rating >= 4:
        result["successful_response_count"] = int(result.get("successful_response_count", 0)) + 1
    return result

def plan_tools(query: str) -> list[str]:
    """Legacy read-only intent helper retained for compatibility with existing tests."""
    q = (query or "").casefold()
    tools = []
    if any(term in q for term in ("my applications", "application status", "applications")):
        tools.append("application_summary")
    if any(term in q for term in ("my interviews", "upcoming interview", "interview schedule")):
        tools.append("interview_summary")
    if any(term in q for term in ("my skills", "my profile", "my resume", "my cv")):
        tools.append("candidate_profile")
    if any(term in q for term in ("recommend jobs", "job recommendations", "jobs for me")):
        tools.append("job_recommendations")
    return tools

def source_memory_is_active(db: Session, memory_id: int | None) -> bool:
    if memory_id is None:
        return True
    source = db.get(AssistantMemory, memory_id)
    if source is None or source.expires_at is None:
        return source is not None
    expires_at = source.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at > datetime.now(timezone.utc)

def build_context(db: Session, user_id: int, query: str, history: list[dict],
                  budget_chars: int = 12000, memories: list[dict] | None = None) -> str:
    fact_rows = db.scalars(select(AssistantFact).where(
        AssistantFact.user_id == user_id, AssistantFact.active.is_(True)).limit(80)).all()
    facts = [fact for fact in fact_rows if source_memory_is_active(db, fact.source_memory_id)]
    memories = memories if memories is not None else retrieve(db, user_id, query, limit=8)
    prefs = preference_snapshot(db, user_id)
    graph_rows = db.scalars(select(AssistantRelation).where(
        AssistantRelation.user_id == user_id).order_by(AssistantRelation.updated_at.desc()).limit(80)).all()
    graph = []
    for edge in graph_rows:
        source = db.get(AssistantEntity, edge.source_entity_id)
        target = db.get(AssistantEntity, edge.target_entity_id)
        if source and target and source_memory_is_active(db, source.source_memory_id) and source_memory_is_active(db, target.source_memory_id):
            graph.append(sanitize(f"{source.name} --{edge.relation_type}--> {target.name}"))
    sections = ["USER FACTS (unverified unless explicitly marked):"]
    for fact in facts:
        fact_value = decrypt_credential(fact.fact_value, purpose=f"assistant-fact:{user_id}") if fact.fact_value_encrypted else fact.fact_value
        sections.append(f"- {fact.fact_key}: {fact_value} (confidence {fact.confidence:.2f}; verified={fact.verified_by_user})")
    sections.append("RELEVANT EPISODIC MEMORY:")
    sections.extend(f"- {item['content']}" for item in memories)
    sections.append("SEMANTIC KNOWLEDGE GRAPH:")
    sections.extend("- " + edge for edge in graph[:40])
    sections.append("PREFERENCES:")
    sections.append(sanitize(str(prefs))[:2000])
    style = sanitize(str(prefs.get("response_style", "")).lower())[:100]
    depth = sanitize(str(prefs.get("technical_depth", "")).lower())[:100]
    if style or depth:
        sections.append("ADAPTIVE RESPONSE GUIDANCE: " + "; ".join(
            item for item in (f"style={style}" if style else "", f"technical_depth={depth}" if depth else "") if item))
    sections.append("RECENT CONVERSATION:")
    sections.extend(f"{item.get('role', 'user')}: {sanitize(item.get('content', ''))[:1800]}" for item in history[-8:])
    return "\n".join(sections)[:budget_chars]
def retrieve(db: Session, user_id: int, query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Tenant-filtered pgvector ANN retrieval with lexical fusion and safe fallback."""
    qvec = embedding(query)
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SET LOCAL hnsw.ef_search = 100"))
        distance = AssistantMemory.embedding_vector.cosine_distance(qvec)
        rows = db.execute(select(AssistantMemory, distance.label("distance")).where(
            AssistantMemory.user_id == user_id,
            AssistantMemory.embedding_vector.is_not(None),
            (AssistantMemory.expires_at.is_(None) | (AssistantMemory.expires_at > __import__("datetime").datetime.now(__import__("datetime").timezone.utc)))
        ).order_by(distance).limit(max(limit * 12, 60))).all()
        ranked = []
        for row, distance_value in rows:
            content = decrypt_credential(row.content, purpose=f"assistant-memory:{user_id}") if row.content_encrypted else row.content
            summary = decrypt_credential(row.summary, purpose=f"assistant-memory:{user_id}") if row.content_encrypted and row.summary else row.summary
            score = 0.62 * max(0.0, 1.0 - float(distance_value)) + 0.38 * min(bm25_score(query, content), 1.0)
            ranked.append((score, row, content, summary))
        legacy_rows = db.scalars(select(AssistantMemory).where(
            AssistantMemory.user_id == user_id,
            AssistantMemory.embedding_vector.is_(None),
            (AssistantMemory.expires_at.is_(None) | (AssistantMemory.expires_at > datetime.now(timezone.utc)))
        ).order_by(AssistantMemory.created_at.desc()).limit(50)).all()
        for row in legacy_rows:
            content = decrypt_credential(row.content, purpose=f"assistant-memory:{user_id}") if row.content_encrypted else row.content
            summary = decrypt_credential(row.summary, purpose=f"assistant-memory:{user_id}") if row.content_encrypted and row.summary else row.summary
            row.embedding_vector = embedding(content)
            lexical = min(bm25_score(query, content), 1.0)
            if lexical > 0:
                ranked.append((0.38 * lexical, row, content, summary))
        if legacy_rows:
            db.flush()
        ranked.sort(key=lambda item: (item[0], item[1].importance), reverse=True)
        shortlist = ranked[:max(limit * 3, 12)]
        cross = _cross_encoder()
        if cross is not None and shortlist:
            try:
                values = cross.predict([(query, item[2][:1800]) for item in shortlist])
                shortlist = sorted([(float(score), item[1], item[2], item[3])
                                    for score, item in zip(values, shortlist)],
                                   key=lambda item: item[0], reverse=True)
            except Exception:
                pass
        return [{"id": row.id, "content": summary or content, "score": round(score, 4),
                 "kind": row.memory_kind} for score, row, content, summary in shortlist[:limit]]
    rows = db.scalars(select(AssistantMemory).where(
        AssistantMemory.user_id == user_id,
        (AssistantMemory.expires_at.is_(None) | (AssistantMemory.expires_at > datetime.now(timezone.utc)))
    ).order_by(AssistantMemory.created_at.desc()).limit(600)).all()
    ranked = []
    for row in rows:
        content = decrypt_credential(row.content, purpose=f"assistant-memory:{user_id}") if row.content_encrypted else row.content
        summary = decrypt_credential(row.summary, purpose=f"assistant-memory:{user_id}") if row.content_encrypted and row.summary else row.summary
        score = 0.58 * cosine(qvec, row.embedding or []) + 0.42 * min(bm25_score(query, content), 1.0)
        ranked.append((score, row, content, summary))
    ranked.sort(key=lambda item: (item[0], item[1].importance), reverse=True)
    return [{"id": row.id, "content": summary or content, "score": round(score, 4),
             "kind": row.memory_kind} for score, row, content, summary in ranked[:limit] if score > 0.015]
