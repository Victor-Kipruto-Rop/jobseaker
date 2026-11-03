from packages.integrations.job_boards.connectors import filter_jobs

JOBS = [
    {"title": "Senior Data Engineer", "description": "Build Spark and Kafka pipelines",
     "location": "Nairobi, Kenya"},
    {"title": "Analytics Engineer", "description": "dbt, SQL and BI models",
     "location": "Remote - Africa"},
    {"title": "Platform Engineer", "description": "Kubernetes and infrastructure",
     "location": "London, UK"},
]

def test_keyword_filter_matches_any_configured_keyword_case_insensitively():
    result = filter_jobs(JOBS, keywords=["SPARK", "dbt"])
    assert [job["title"] for job in result] == ["Senior Data Engineer", "Analytics Engineer"]

def test_location_filter_uses_location_and_description():
    assert [job["title"] for job in filter_jobs(JOBS, location="nairobi")] == ["Senior Data Engineer"]

def test_remote_filter_is_explicit_and_excludes_onsite_roles():
    assert [job["title"] for job in filter_jobs(JOBS, remote_only=True)] == ["Analytics Engineer"]

def test_empty_filters_preserve_all_normalized_jobs():
    assert filter_jobs(JOBS) == JOBS
