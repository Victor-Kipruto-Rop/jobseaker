from packages.ai.agents.job_matching.agent import score_job

def test_role_skill_coverage_is_explainable_and_bounded():
    result = score_job("Senior Data Engineer", "Build Python, SQL, Kafka and Airflow pipelines.", ["python", "SQL", "Apache Kafka"])
    assert result["fit_score"] == 75
    assert set(result["matched_skills"]) == {"kafka", "python", "sql"}
    assert set(result["missing_skills"]) == {"airflow"}
    assert result["method"] == "transparent_role_skill_coverage_v2"
    assert 0 <= result["coverage_percent"] <= 100

def test_skill_aliases_are_normalized():
    result = score_job("Data Engineer", "Use PostgreSQL, Apache Spark and dbt.", ["postgres", "spark", "dbt core"])
    assert {"postgresql", "apache spark", "dbt"}.issubset(set(result["matched_skills"]))

def test_skill_matching_uses_word_boundaries():
    result = score_job("Data Engineer", "Experience with SQL and JavaScript is useful.", ["java"])
    assert "java" not in result["matched_skills"]

def test_empty_taxonomy_match_is_low_confidence_not_fake_perfect_fit():
    result = score_job("Analyst", "Strong communication and stakeholder management.", ["python"])
    assert result["fit_score"] == 0
    assert result["required_skill_count"] == 0
    assert result["confidence"] == "low"
