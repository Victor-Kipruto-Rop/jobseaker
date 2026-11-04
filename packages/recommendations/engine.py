"""Hybrid career recommendation engine.

Implements collaborative filtering, TF-IDF, optional sentence-transformer
embeddings, knowledge-graph traversal, optional LightGBM learning-to-rank,
and Thompson/UCB bandit exploration. The deterministic paths work without
optional ML packages and never claim to predict hiring outcomes.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable

from packages.recommendations.skill_graph import skill_match_score

TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.]{1,40}")
POSITIVE = {"click": 1.0, "view": 0.25, "save": 3.0, "apply": 4.0,
            "interview": 5.0, "offer": 6.0}
NEGATIVE = {"dismiss": -1.5, "skip": -0.4}
FEATURE_NAMES = (
    "tfidf", "semantic", "skill_overlap", "role_match", "location_match",
    "remote_match", "salary_match", "company_affinity", "recency",
    "user_cf", "item_cf", "graph", "bandit", "skill_graph",
)


def tokens(text: str) -> list[str]:
    return [x.lower() for x in TOKEN_RE.findall(text or "")]


def document_text(job: dict[str, Any]) -> str:
    return " ".join(str(x or "") for x in (
        job.get("title"), job.get("company"), job.get("description"),
        " ".join(job.get("required_skills") or []), job.get("location"),
        job.get("employment_type"), job.get("remote_type"),
    ))


def tfidf_vectors(documents: list[str]) -> list[dict[str, float]]:
    tokenized = [tokens(doc) for doc in documents]
    df: Counter[str] = Counter()
    for row in tokenized:
        df.update(set(row))
    n_docs = max(len(tokenized), 1)
    vectors = []
    for row in tokenized:
        counts = Counter(row)
        length = max(sum(counts.values()), 1)
        vectors.append({
            term: (count / length) * (math.log((n_docs + 1) / (df[term] + 1)) + 1.0)
            for term, count in counts.items()
        })
    return vectors


def cosine(left: dict[str, float] | list[float], right: dict[str, float] | list[float]) -> float:
    if isinstance(left, dict) and isinstance(right, dict):
        if not left or not right:
            return 0.0
        common = left.keys() & right.keys()
        numerator = sum(left[k] * right[k] for k in common)
        lnorm = math.sqrt(sum(v * v for v in left.values()))
        rnorm = math.sqrt(sum(v * v for v in right.values()))
    else:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(float(a) * float(b) for a, b in zip(left, right))
        lnorm = math.sqrt(sum(float(v) ** 2 for v in left))
        rnorm = math.sqrt(sum(float(v) ** 2 for v in right))
    return max(0.0, min(1.0, numerator / (lnorm * rnorm))) if lnorm and rnorm else 0.0


def normalized_skill_set(values: Iterable[str]) -> set[str]:
    return {" ".join(tokens(v)) for v in values if v and tokens(v)}


def role_similarity(job_title: str, target_roles: Iterable[str]) -> float:
    title = set(tokens(job_title))
    targets = [set(tokens(x)) for x in target_roles if x]
    if not title or not targets:
        return 0.0
    return max((len(title & target) / max(len(title | target), 1) for target in targets), default=0.0)


def location_score(job: dict[str, Any], preferences: dict[str, Any], candidate_location: str) -> float:
    loc = (job.get("location") or "").lower()
    wanted = (preferences.get("locations") or preferences.get("location") or candidate_location or "")
    wanted_values = wanted if isinstance(wanted, list) else [wanted]
    remote = (job.get("remote_type") or "").lower()
    mode = (preferences.get("work_mode") or preferences.get("remote_type") or "").lower()
    if any(x in remote for x in ("remote", "distributed")) and mode in {"remote", "hybrid", "any"}:
        return 1.0
    if not wanted_values or not loc:
        return 0.35
    return 1.0 if any(str(x).lower() in loc or loc in str(x).lower() for x in wanted_values if x) else 0.0


def salary_score(job: dict[str, Any], preferences: dict[str, Any]) -> float:
    minimum = preferences.get("salary_min")
    maximum = preferences.get("salary_max")
    low, high = job.get("salary_min"), job.get("salary_max")
    if minimum is None and maximum is None:
        return 0.5
    if low is None and high is None:
        return 0.35
    low = low if low is not None else high
    high = high if high is not None else low
    if minimum is not None and high < minimum:
        return 0.0
    if maximum is not None and low > maximum:
        return 0.0
    return 1.0


def recency_score(job: dict[str, Any], now: datetime | None = None) -> float:
    posted = job.get("posted_at")
    if not posted:
        return 0.35
    if isinstance(posted, str):
        try:
            posted = datetime.fromisoformat(posted.replace("Z", "+00:00"))
        except ValueError:
            return 0.35
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    age_days = max(0.0, ((now or datetime.now(timezone.utc)) - posted).total_seconds() / 86400)
    return math.exp(-age_days / 21.0)


def item_key(job: dict[str, Any]) -> str:
    url = (job.get("source_url") or "").strip().lower()
    if url:
        return url
    raw = "|".join(str(job.get(k) or "").strip().lower() for k in ("company", "title", "location"))
    return "derived:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _event_weight(event: dict[str, Any]) -> float:
    kind = str(event.get("event_type") or "").lower()
    return POSITIVE.get(kind, NEGATIVE.get(kind, 0.0))


def collaborative_scores(
    user_id: int, events: list[dict[str, Any]], candidate_keys: set[str],
    min_cohort: int = 3,
) -> tuple[dict[str, float], dict[str, float]]:
    """User-user cosine and item-item co-interaction similarity.

    The user-user path only emits signals for item cohorts with at least
    min_cohort distinct peers, avoiding disclosure of a single person's activity.
    """
    by_user: dict[int, dict[str, float]] = defaultdict(dict)
    by_item: dict[str, dict[int, float]] = defaultdict(dict)
    for event in events:
        uid = int(event.get("user_id") or 0)
        key = str(event.get("item_key") or "")
        weight = _event_weight(event)
        if not uid or not key or not weight:
            continue
        by_user[uid][key] = max(by_user[uid].get(key, 0.0), weight)
        by_item[key][uid] = max(by_item[key].get(uid, 0.0), weight)
    mine = by_user.get(user_id, {})
    seen = set(mine)
    peers = []
    for uid, vector in by_user.items():
        if uid == user_id:
            continue
        sim = cosine(mine, vector)
        if sim > 0:
            peers.append((uid, sim, vector))
    user_scores: dict[str, float] = defaultdict(float)
    cohort_count: Counter[str] = Counter()
    for uid, similarity, vector in peers:
        for key, weight in vector.items():
            if key not in seen and weight > 0:
                user_scores[key] += similarity * weight
                cohort_count[key] += 1
    user_scores = {
        key: score / max(cohort_count[key], 1)
        for key, score in user_scores.items()
        if cohort_count[key] >= min_cohort and key in candidate_keys
    }

    item_scores: dict[str, float] = defaultdict(float)
    positive_seeds = [key for key, weight in mine.items() if weight > 0]
    for seed in positive_seeds:
        seed_users = by_item.get(seed, {})
        for candidate, candidate_users in by_item.items():
            if candidate == seed or candidate in seen or candidate not in candidate_keys:
                continue
            overlap = set(seed_users) & set(candidate_users)
            if len(overlap) < min_cohort:
                continue
            similarity = cosine(
                {str(k): v for k, v in seed_users.items()},
                {str(k): v for k, v in candidate_users.items()},
            )
            item_scores[candidate] += similarity * mine[seed]
    return dict(user_scores), dict(item_scores)


def graph_scores(
    user_id: int, jobs: list[dict[str, Any]], events: list[dict[str, Any]],
) -> dict[str, float]:
    """Two/three-hop knowledge graph traversal: user→job→company/skill→job."""
    by_key = {item_key(job): job for job in jobs}
    positive = {
        str(event.get("item_key")) for event in events
        if int(event.get("user_id") or 0) == user_id and _event_weight(event) > 0
    }
    company_to_jobs: dict[str, set[str]] = defaultdict(set)
    skill_to_jobs: dict[str, set[str]] = defaultdict(set)
    for key, job in by_key.items():
        company = str(job.get("company_domain") or job.get("company") or "").lower()
        if company:
            company_to_jobs[company].add(key)
        for skill in normalized_skill_set(job.get("required_skills") or []):
            skill_to_jobs[skill].add(key)
    scores: dict[str, float] = defaultdict(float)
    for seed in positive:
        job = by_key.get(seed)
        if not job:
            continue
        company = str(job.get("company_domain") or job.get("company") or "").lower()
        if company:
            for key in company_to_jobs[company] - positive:
                scores[key] += 0.75
        for skill in normalized_skill_set(job.get("required_skills") or []):
            for key in skill_to_jobs[skill] - positive:
                scores[key] += 0.25
    maximum = max(scores.values(), default=1.0)
    return {key: min(value / maximum, 1.0) for key, value in scores.items()}


@lru_cache(maxsize=1)
def _sentence_model():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    except Exception:
        return None


def semantic_embeddings(texts: list[str]) -> list[list[float]]:
    model = _sentence_model()
    if model is None:
        return []
    try:
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [[float(v) for v in row] for row in vectors]
    except Exception:
        return []


def bandit_scores(events: list[dict[str, Any]], arms: Iterable[str]) -> dict[str, float]:
    """Blend Thompson Sampling and UCB1 over recommendation-channel rewards."""
    stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for event in events:
        arm = str(event.get("recommendation_source") or "")
        kind = str(event.get("event_type") or "")
        if arm not in set(arms):
            continue
        if kind == "impression":
            stats[arm][1] += 1
        elif kind in {"click", "save", "apply", "interview", "offer"}:
            stats[arm][0] += 1
    total = max(sum(v[1] for v in stats.values()), 1)
    result = {}
    for arm in arms:
        rewards, impressions = stats[arm]
        alpha, beta = 1 + rewards, 1 + max(impressions - rewards, 0)
        thompson = random.betavariate(alpha, beta)
        ucb = (rewards / impressions + math.sqrt(2 * math.log(total + 1) / impressions)
               if impressions else 1.0)
        result[arm] = 0.5 * thompson + 0.5 * min(ucb, 1.0)
    maximum = max(result.values(), default=1.0)
    return {key: value / maximum if maximum else 0.0 for key, value in result.items()}


def train_ltr_model(samples: list[dict[str, Any]]):
    """Train an optional LightGBM binary ranker from explicit feedback snapshots."""
    if len(samples) < 40:
        return None
    labels = [int(bool(row.get("label"))) for row in samples]
    if sum(labels) < 5 or len(labels) - sum(labels) < 5:
        return None
    try:
        from lightgbm import LGBMClassifier
        model = LGBMClassifier(
            n_estimators=80, max_depth=4, learning_rate=0.04,
            num_leaves=15, verbosity=-1, class_weight="balanced",
        )
        model.fit(
            [[float(row.get("features", {}).get(name, 0.0)) for name in FEATURE_NAMES]
             for row in samples],
            labels,
        )
        return model
    except Exception:
        return None


def ltr_score(model: Any, features: dict[str, float]) -> float | None:
    if model is None:
        return None
    try:
        return float(model.predict_proba(
            [[float(features.get(name, 0.0)) for name in FEATURE_NAMES]]
        )[0][1])
    except Exception:
        return None


def rank_opportunities(
    user_id: int,
    profile: dict[str, Any],
    skills: list[str],
    resume_text: str,
    jobs: list[dict[str, Any]],
    events: list[dict[str, Any]],
    training_samples: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Score and explain a candidate's active job set using hybrid retrieval."""
    if not jobs:
        return []
    preferences = profile.get("preferences") or {}
    target_roles = profile.get("target_roles") or []
    candidate_location = profile.get("location") or ""
    # Recent positive interactions contribute job language to the profile query.
    by_key = {item_key(job): job for job in jobs}
    recent_profile_terms = []
    for event in sorted(events, key=lambda row: str(row.get("created_at") or ""), reverse=True)[:300]:
        if int(event.get("user_id") or 0) != user_id:
            continue
        interacted = by_key.get(str(event.get("item_key") or ""))
        if interacted and _event_weight(event) > 0:
            recent_profile_terms.extend([document_text(interacted)] * min(3, max(1, round(_event_weight(event)))))
    profile_text = " ".join([
        profile.get("headline") or "", profile.get("summary") or "",
        " ".join(target_roles), " ".join(skills), resume_text[:12000],
        " ".join(str(x) for x in (preferences.get("keywords") or [])),
        " ".join(recent_profile_terms[:60]),
    ])
    documents = [profile_text] + [document_text(job) for job in jobs]
    vectors = tfidf_vectors(documents)
    content_scores = [cosine(vectors[0], vector) for vector in vectors[1:]]
    keys = {item_key(job) for job in jobs}
    user_cf, item_cf = collaborative_scores(user_id, events, keys)
    graph = graph_scores(user_id, jobs, events)
    bandits = bandit_scores(events, ("content", "collaborative", "semantic", "graph", "fresh"))
    cached = [job.get("semantic_embedding") or [] for job in jobs]
    cached_dimension = len(cached[0]) if cached else 0
    query_embedding = jobs[0].get("_profile_embedding") if jobs else None
    if query_embedding and cached_dimension and all(len(vector) == cached_dimension for vector in cached):
        embeddings = [query_embedding] + cached
        semantic_available = True
    else:
        embeddings = semantic_embeddings(documents)
        semantic_available = len(embeddings) == len(documents)
    model = train_ltr_model(training_samples or [])
    results = []
    for index, job in enumerate(jobs):
        key = item_key(job)
        required = normalized_skill_set(job.get("required_skills") or [])
        candidate = normalized_skill_set(skills)
        detected = required or normalized_skill_set(tokens(document_text(job)))
        matched = sorted(candidate & detected)
        missing = sorted(detected - candidate)
        overlap = len(matched) / max(len(detected), 1) if detected else 0.0
        graph_skill_score, graph_skill_evidence = skill_match_score(
            skills, job.get("required_skills") or [],
        )
        role = role_similarity(job.get("title") or "", target_roles)
        location = location_score(job, preferences, candidate_location)
        remote_pref = str(preferences.get("work_mode") or "").lower()
        remote = str(job.get("remote_type") or "").lower()
        remote_match = 1.0 if not remote_pref or remote_pref == "any" else (
            1.0 if remote_pref in remote or (remote_pref == "remote" and remote in {"remote", "distributed"})
            else 0.0
        )
        salary = salary_score(job, preferences)
        company = str(job.get("company_domain") or job.get("company") or "").lower()
        liked_companies = {
            str(x.get("company_domain") or x.get("company") or "").lower()
            for x in jobs if item_key(x) in {
                str(e.get("item_key")) for e in events
                if int(e.get("user_id") or 0) == user_id and _event_weight(e) > 0
            }
        }
        company_affinity = 1.0 if company and company in liked_companies else 0.0
        recency = recency_score(job)
        semantic = float(job.get("_pgvector_similarity", 0.0)) or (
            cosine(embeddings[0], embeddings[index + 1]) if semantic_available else 0.0
        )
        features = {
            "tfidf": content_scores[index], "semantic": semantic,
            "skill_overlap": overlap, "role_match": role,
            "location_match": location, "remote_match": remote_match,
            "salary_match": salary, "company_affinity": company_affinity,
            "recency": recency, "user_cf": user_cf.get(key, 0.0),
            "item_cf": item_cf.get(key, 0.0), "graph": graph.get(key, 0.0),
            "bandit": max(bandits.values(), default=0.0),
            "skill_graph": graph_skill_score,
        }
        weights = {
            "tfidf": 0.16, "semantic": 0.14 if semantic_available else 0.0,
            "skill_overlap": 0.19, "role_match": 0.15, "location_match": 0.10,
            "remote_match": 0.06, "salary_match": 0.04, "company_affinity": 0.03,
            "recency": 0.06, "user_cf": 0.04, "item_cf": 0.04, "graph": 0.04,
            "bandit": 0.04, "skill_graph": 0.08,
        }
        total_weight = sum(weights.values())
        hybrid = sum(features[name] * weight for name, weight in weights.items()) / total_weight
        learned = ltr_score(model, features)
        score = learned if learned is not None else hybrid
        signals = []
        if matched:
            signals.append(f"Matches {len(matched)} recorded skills")
        if graph_skill_evidence:
            signals.append("Recognizes equivalent or related skills in your career profile")
        if role:
            signals.append("Related to your target roles")
        if location >= 0.8:
            signals.append("Matches your location or work-mode preference")
        if features["user_cf"] or features["item_cf"]:
            signals.append("Similar candidates' interactions support this role")
        if features["graph"]:
            signals.append("Connected to companies or skills in your career graph")
        if recency >= 0.7:
            signals.append("Recently published")
        if semantic_available and semantic >= 0.35:
            signals.append("Semantically related to your career profile")
        missing_fields = []
        if not job.get("salary_min") and not job.get("salary_max"):
            missing_fields.append("salary")
        if not job.get("posted_at"):
            missing_fields.append("posting date")
        source_candidates = {
            "content": max(features["tfidf"], features["skill_overlap"], features["role_match"]),
            "collaborative": max(features["user_cf"], features["item_cf"]),
            "semantic": features["semantic"],
            "graph": features["graph"],
            "fresh": features["recency"],
        }
        source_candidates = {
            name: value * (0.5 + 0.5 * bandits.get(name, 0.5))
            for name, value in source_candidates.items()
        }
        recommendation_source = max(source_candidates, key=source_candidates.get)
        results.append({
            **job,
            "item_key": key,
            "recommendation_source": recommendation_source,
            "recommendation_score": round(max(0.0, min(score, 1.0)) * 100, 1),
            "recommendation_method": "lightgbm_ltr" if learned is not None else "hybrid_personalized",
            "features": {k: round(float(v), 4) for k, v in features.items()},
            "explanation": {
                "why_recommended": signals or ["Relevant to your saved opportunity and career profile data"],
                "matched_skills": matched,
                "related_skill_matches": graph_skill_evidence,
                "skill_gaps": missing[:12],
                "data_gaps": missing_fields,
                "confidence": "learned" if learned is not None else (
                    "semantic_and_behavioral" if semantic_available and events else "profile_and_content"
                ),
                "limitations": [
                    "This is a relevance estimate, not a hiring-probability prediction.",
                    "Skill matches are inferred from text and your recorded profile; verify each requirement.",
                ],
            },
        })
    ranked = sorted(results, key=lambda row: row["recommendation_score"], reverse=True)
    # Reserve 18% of the feed for recently published roles with no candidate interaction.
    interacted = {str(e.get("item_key") or "") for e in events
                  if int(e.get("user_id") or 0) == user_id}
    fresh = [row for row in ranked if row["item_key"] not in interacted
             and recency_score(row) >= math.exp(-14.0 / 21.0)]
    if len(ranked) >= 5 and fresh:
        quota = min(len(fresh), max(1, math.ceil(len(ranked) * 0.18)))
        random.shuffle(fresh)
        selected = {row["item_key"] for row in fresh[:quota]}
        explore = [row for row in fresh if row["item_key"] in selected]
        exploit = [row for row in ranked if row["item_key"] not in selected]
        merged = []
        ei = xi = 0
        interval = max(2, round(1.0 / 0.18))
        while ei < len(explore) or xi < len(exploit):
            if ei < len(explore) and len(merged) % interval == interval - 1:
                row = explore[ei]
                row["recommendation_exploration"] = True
                row["recommendation_explanation"] = "Exploration slot: recent role without prior interaction history"
                merged.append(row)
                ei += 1
            elif xi < len(exploit):
                merged.append(exploit[xi])
                xi += 1
            else:
                row = explore[ei]
                row["recommendation_exploration"] = True
                row["recommendation_explanation"] = "Exploration slot: recent role without prior interaction history"
                merged.append(row)
                ei += 1
        ranked = merged
    return ranked
