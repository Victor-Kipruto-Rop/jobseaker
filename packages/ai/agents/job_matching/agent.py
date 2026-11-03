import re

JOB_SKILL_TAXONOMY = (
    "apache spark", "data modeling", "data warehousing", "machine learning",
    "great expectations", "delta lake", "power bi", "data quality", "bigquery",
    "postgresql", "databricks", "kubernetes", "snowflake", "redshift",
    "terraform", "airflow", "kafka", "python", "sql", "etl", "elt", "dbt",
    "flink", "hadoop", "hive", "iceberg", "pandas", "numpy", "docker",
    "aws", "azure", "gcp", "java", "scala", "tableau", "excel", "statistics",
    "linux", "bash", "git", "mysql", "graphql", "rest api",
)

ALIASES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "spark": "apache spark",
    "apache spark": "apache spark",
    "powerbi": "power bi",
    "google cloud": "gcp",
    "amazon web services": "aws",
    "microsoft azure": "azure",
}

def _normalize(value: str) -> str:
    normalized = " ".join(value.lower().strip().split())
    return ALIASES.get(normalized, normalized)

def _contains(text: str, term: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None

def score_job(title: str, description: str, skills: list[str]) -> dict:
    """Explainable keyword fit: candidate evidence against skills explicitly present in a role."""
    text = f"{title} {description}"
    candidate = {_normalize(skill) for skill in skills if skill.strip()}
    required = sorted({_normalize(term) for term in JOB_SKILL_TAXONOMY if _contains(text, term)})
    matched = [term for term in required if term in candidate]
    missing = [term for term in required if term not in candidate]
    score = round(100 * len(matched) / len(required)) if required else 0
    return {
        "title": title,
        "fit_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "required_skills_detected": required,
        "method": "transparent_role_skill_coverage",
        "warning": (
            "Keyword coverage only. The score does not verify proficiency, seniority, "
            "experience, education, eligibility, or hiring probability."
        ),
    }
