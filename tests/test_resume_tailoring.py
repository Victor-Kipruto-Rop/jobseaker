from packages.resumes.tailoring import tailor_resume, validate_grounded_draft

def test_resume_reordering_uses_only_source_sentences():
    source = "Built Python ETL pipelines. Managed PostgreSQL reports."
    result = tailor_resume(source, "Python ETL pipelines and SQL")
    assert result["items"]
    assert all(item["text"] in source for item in result["items"])
    assert result["claims_invented"] is False

def test_resume_tailoring_requires_documents():
    try:
        tailor_resume("", "Python engineer")
    except ValueError:
        return
    raise AssertionError("empty resume must be rejected")

def test_numeric_claim_guard():
    result = validate_grounded_draft("Improved speed by 45%.", "Built Python pipelines.")
    assert result["grounded"] is False
    assert "45%" in result["unsupported_claims"]
