from packages.ai.agents.job_matching.agent import score_job
def test_job_match_score_is_explainable():
    result=score_job("Data Engineer","Python SQL ETL pipelines",["Python","SQL","Kafka"])
    assert result["fit_score"]==67
    assert result["matched_skills"]==["Python","SQL"]
