"""Small explainable skill ontology with bounded equivalence traversal."""
from __future__ import annotations
from collections import deque
from typing import Iterable

# Edges are curated equivalences/parent concepts, not claims of identical proficiency.
SKILL_GRAPH: dict[str, set[str]] = {
    "postgresql": {"sql", "relational databases", "database systems"},
    "mysql": {"sql", "relational databases", "database systems"},
    "sql server": {"sql", "relational databases", "database systems"},
    "snowflake": {"sql", "data warehousing", "cloud data platforms"},
    "bigquery": {"sql", "data warehousing", "cloud data platforms"},
    "redshift": {"sql", "data warehousing", "cloud data platforms"},
    "apache kafka": {"event streaming", "distributed systems", "data engineering"},
    "redpanda": {"event streaming", "distributed systems", "data engineering"},
    "airflow": {"workflow orchestration", "data engineering"},
    "dagster": {"workflow orchestration", "data engineering"},
    "dbt": {"analytics engineering", "data transformation", "sql"},
    "pandas": {"python", "data manipulation", "data analysis"},
    "polars": {"python", "data manipulation", "data analysis"},
    "pyspark": {"python", "distributed processing", "data engineering"},
    "spark": {"distributed processing", "data engineering"},
    "aws": {"cloud computing"},
    "azure": {"cloud computing"},
    "gcp": {"cloud computing"},
}


def normalize_skill(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").split())


def expand_skills(values: Iterable[str], *, max_depth: int = 2) -> dict[str, int]:
    """Return canonical related terms and graph distance, retaining the best path."""
    if max_depth < 0 or max_depth > 4:
        raise ValueError("max_depth must be between 0 and 4")
    distances: dict[str, int] = {}
    queue = deque((normalize_skill(v), 0) for v in values if normalize_skill(v))
    while queue:
        node, depth = queue.popleft()
        if node in distances and distances[node] <= depth:
            continue
        distances[node] = depth
        if depth >= max_depth:
            continue
        for neighbor in SKILL_GRAPH.get(node, set()):
            if neighbor not in distances or distances[neighbor] > depth + 1:
                queue.append((neighbor, depth + 1))
    return distances


def skill_match_score(candidate_skills: Iterable[str], required_skills: Iterable[str]) -> tuple[float, list[dict]]:
    expanded = expand_skills(candidate_skills)
    required = sorted({normalize_skill(v) for v in required_skills if normalize_skill(v)})
    if not required:
        return 0.0, []
    matched = []
    for skill in required:
        distance = expanded.get(skill)
        if distance is not None:
            matched.append({"required": skill, "distance": distance,
                            "weight": round(1.0 / (distance + 1), 3)})
    return sum(x["weight"] for x in matched) / len(required), matched
