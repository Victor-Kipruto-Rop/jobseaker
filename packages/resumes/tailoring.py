"""Fact-preserving resume relevance ordering."""
import re
from collections import Counter

STOP = {"the", "and", "for", "with", "you", "your", "are", "will", "from", "that", "this", "have", "has", "job", "role"}

def terms(value):
    return [w for w in re.findall(r"[a-z][a-z0-9+#.-]{1,}", (value or "").casefold()) if w not in STOP]

def tailor_resume(source_text, job_description, max_chars=30000):
    source = (source_text or "")[:max_chars]
    description = (job_description or "")[:max_chars]
    if not source.strip() or not description.strip():
        raise ValueError("Resume text and job description are required")
    wanted = Counter(terms(description))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\\s+|\\n+", source) if s.strip()]
    ranked = []
    for index, sentence in enumerate(sentences):
        counts = Counter(terms(sentence))
        overlap = sum(min(count, wanted[word]) for word, count in counts.items())
        ranked.append({"source_index": index, "text": sentence,
                       "relevance": round(overlap / max(1, len(counts)), 4)})
    ranked.sort(key=lambda row: (-row["relevance"], row["source_index"]))
    return {"strategy": "evidence_preserving_reorder",
            "items": [row for row in ranked if row["relevance"] > 0][:40],
            "matched_terms": sorted(set(terms(description)) & set(terms(source))),
            "unmatched_job_terms": sorted(set(terms(description)) - set(terms(source))),
            "claims_invented": False, "requires_candidate_review": True}

def validate_grounded_draft(draft, source_text):
    source = source_text or ""
    numbers = re.findall(r"\\b(?:\\d+(?:\\.\\d+)?%?|20\\d{2}|19\\d{2})\\b", draft or "")
    unsupported = [item for item in numbers if item not in source]
    return {"grounded": not unsupported, "unsupported_claims": unsupported,
            "requires_candidate_review": True}
