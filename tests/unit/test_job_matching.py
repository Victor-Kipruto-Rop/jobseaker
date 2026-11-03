from packages.ai.agents.job_matching.agent import score_job

def test_job_match_score_is_explainable():
    result = score_job("Data Engineer", "Python SQL ETL pipelines", ["Python", "SQL", "Kafka"])
    assert result["fit_score"] == 67
    assert result["matched_skills"] == ["python", "sql"]
    assert result["missing_skills"] == ["etl"]
    assert result["method"] == "transparent_role_skill_coverage"

def test_no_detected_requirements_does_not_claim_a_match():
    result = score_job("Operations role", "Coordinate meetings and prepare reports", ["Python"])
    assert result["fit_score"] == 0
    assert result["required_skills_detected"] == []
