from packages.resumes.cover_letter import build_cover_letter

def test_cover_letter_uses_only_existing_resume_evidence():
    source = "Built Python ETL pipelines. Managed PostgreSQL reporting."
    result = build_cover_letter(source, "Python ETL pipelines and SQL", "Data Engineer", "Example Ltd")
    assert "Data Engineer" in result["content"]
    assert all(sentence in source for sentence in result["evidence_sentences"])
    assert result["claims_invented"] is False
    assert result["requires_candidate_review"] is True

def test_cover_letter_rejects_no_relevant_evidence():
    try:
        build_cover_letter("Worked in retail sales.", "Kubernetes distributed systems", "Platform Engineer")
    except ValueError:
        return
    raise AssertionError("must not generate unsupported experience")
