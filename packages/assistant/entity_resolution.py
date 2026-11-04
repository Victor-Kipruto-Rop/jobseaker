"""Tenant-scoped entity extraction, canonicalization and conservative resolution."""
from __future__ import annotations
import re
from difflib import SequenceMatcher
from sqlalchemy import select
from sqlalchemy.orm import Session
from packages.database.models.assistant import AssistantEntity, AssistantRelation

ALIASES = {
    "python": {"py"}, "postgresql": {"postgres", "psql"}, "javascript": {"js"},
    "typescript": {"ts"}, "amazon web services": {"aws"}, "google cloud platform": {"gcp"},
    "microsoft azure": {"azure"}, "apache kafka": {"kafka"}, "power bi": {"powerbi"},
    "machine learning": {"ml"}, "scikit-learn": {"sklearn"},
}
SKILLS = sorted(set(ALIASES) | {"sql","java","go","rust","elixir","airflow","dbt","spark",
    "pandas","docker","kubernetes","fastapi","flask","react","next.js","redis",
    "snowflake","databricks","terraform","git","linux","excel","tableau"}, key=len, reverse=True)

def normalize(value: str) -> str:
    value = value.casefold().strip()
    value = re.sub(r"\b(incorporated|limited|ltd|inc|llc|plc)\b", "", value)
    return re.sub(r"[^a-z0-9+#.]+", " ", value).strip()[:240]

def extract_entities(text: str) -> list[tuple[str, str]]:
    found = set()
    for skill in SKILLS:
        if re.search(r"(?<![\w+#.])" + re.escape(skill) + r"(?![\w+#.])", text or "", re.I):
            found.add(("skill", skill))
    patterns = [
        ("employer", r"\b(?:worked at|working at|employed by|interned at)\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,4})"),
        ("project", r"\b(?:project|built|building|maintain)\s+(?:called\s+)?([A-Z][\w.-]*(?:\s+[A-Z][\w.-]*){0,3})"),
        ("role", r"\b(?:target role|role|position)\s*(?:is|:|as)?\s+([A-Z][\w/&+.-]*(?:\s+[A-Z][\w/&+.-]*){0,3})"),
    ]
    for kind, pattern in patterns:
        for match in re.finditer(pattern, text or ""):
            value = match.group(1).strip(" .,:;")
            if 2 <= len(value) <= 160:
                found.add((kind, value))
    return sorted(found)

def resolve_entity(db: Session, user_id: int, entity_type: str, name: str,
                   memory_id: int | None = None) -> AssistantEntity:
    normalized = normalize(name)
    aliases = ALIASES.get(normalized, set())
    rows = db.scalars(select(AssistantEntity).where(
        AssistantEntity.user_id == user_id, AssistantEntity.entity_type == entity_type)).all()
    match = next((row for row in rows if row.normalized_name in
                  {normalized, *(normalize(x) for x in aliases)}
                  or normalized in (row.attributes or {}).get("aliases", [])), None)
    if match is None:
        ranked = sorted(((SequenceMatcher(None, normalized, row.normalized_name).ratio(), row)
                         for row in rows), key=lambda item: item[0], reverse=True)
        if ranked and ranked[0][0] >= 0.94 and (len(ranked) == 1 or ranked[0][0]-ranked[1][0] >= 0.04):
            match = ranked[0][1]
    if match is None:
        match = AssistantEntity(user_id=user_id, entity_type=entity_type, name=name[:240],
            normalized_name=normalized, attributes={"aliases": sorted(aliases)}, source_memory_id=memory_id)
        db.add(match)
        db.flush()
    else:
        attrs = dict(match.attributes or {})
        attrs["aliases"] = sorted(set(attrs.get("aliases", [])) | aliases |
                                  ({normalized} if normalized != match.normalized_name else set()))
        match.attributes = attrs
        if memory_id and not match.source_memory_id:
            match.source_memory_id = memory_id
    return match

def index_entities(db: Session, user_id: int, text: str, memory_id: int | None = None) -> int:
    candidate = resolve_entity(db, user_id, "candidate", "Candidate", memory_id)
    count = 0
    for kind, name in extract_entities(text):
        entity = resolve_entity(db, user_id, kind, name, memory_id)
        edge = db.scalar(select(AssistantRelation).where(
            AssistantRelation.user_id == user_id, AssistantRelation.source_entity_id == candidate.id,
            AssistantRelation.target_entity_id == entity.id, AssistantRelation.relation_type == "has_" + kind))
        if edge is None:
            db.add(AssistantRelation(user_id=user_id, source_entity_id=candidate.id,
                target_entity_id=entity.id, relation_type="has_" + kind, confidence=0.72))
        count += 1
    return count
