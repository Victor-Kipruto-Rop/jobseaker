import re

# Deliberately transparent deterministic taxonomy. These are matching signals,
# not proof of candidate proficiency or a prediction of hiring outcomes.
JOB_SKILL_TAXONOMY = (
    "apache spark", "spark sql", "data modeling", "dimensional modeling",
    "data warehousing", "data warehouse", "machine learning", "great expectations",
    "delta lake", "power bi", "powerbi", "data quality", "bigquery", "google bigquery", "postgres", "postgresql",
    "databricks", "kubernetes", "snowflake", "redshift", "terraform",
    "airflow", "kafka", "spark", "python", "sql", "etl", "elt", "dbt", "flink",
    "hadoop", "hive", "iceberg", "pandas", "numpy", "docker", "aws", "amazon web services", "amazon s3",
    "azure", "microsoft azure", "gcp", "google cloud", "java", "scala", "tableau", "excel", "statistics",
    "linux", "bash", "git", "mysql", "graphql", "rest api", "airbyte",
    "dagster", "prefect", "fivetran", "trino", "presto", "athena",
    "aws glue", "aws emr", "s3", "azure data factory", "synapse analytics",
    "microsoft fabric", "dataflow", "pub sub", "cloud composer",
    "google cloud storage", "google cloud dataflow", "spark streaming", "kafka connect",
    "debezium", "data contracts", "schema registry",
    "data governance", "data observability", "data lineage",
)

ALIASES = {
    "postgres": "postgresql", "postgresql": "postgresql",\n    "data warehouse": "data warehousing",
    "apache kafka": "kafka", "apache airflow": "airflow",
    "spark": "apache spark", "apache spark": "apache spark",
    "powerbi": "power bi", "google cloud": "gcp", "google bigquery": "bigquery",
    "amazon web services": "aws", "microsoft azure": "azure",
    "dbt core": "dbt",
    "amazon s3": "s3", "aws s3": "s3",
    "azure data factory (adf)": "azure data factory",
    "google cloud dataflow": "dataflow",
    "apache iceberg": "iceberg", "apache flink": "flink",
}

def _normalize(value: str) -> str:
    normalized = " ".join(value.lower().strip().split())
    return ALIASES.get(normalized, normalized)

def _contains(text: str, term: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(term.strip()) + r"(?![a-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None

def score_job(title: str, description: str, skills: list[str]) -> dict:
    """Explainable role-skill coverage with explicit evidence limitations."""
    text = f"{title} {description}"
    candidate = {_normalize(skill) for skill in skills if skill and skill.strip()}
    required = sorted({_normalize(term) for term in JOB_SKILL_TAXONOMY if _contains(text, term)})
    matched = [term for term in required if term in candidate]
    missing = [term for term in required if term not in candidate]
    score = round(100 * len(matched) / len(required)) if required else 0
    return {
        "title": title,
        "fit_score": score,
        "coverage_percent": score,
        "matched_skill_count": len(matched),
        "required_skill_count": len(required),
        "matched_skills": matched,
        "missing_skills": missing,
        "required_skills_detected": required,
        "method": "transparent_role_skill_coverage_v2",
        "confidence": "low" if not required else "keyword_only",
        "warning": (
            "Keyword coverage only. Skills are matched by text and recorded profile entries. "
            "The score does not verify proficiency, seniority, experience, education, eligibility, "
            "company quality, role suitability, or hiring probability."
        ),
    }
