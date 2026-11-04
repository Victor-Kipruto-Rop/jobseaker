from packages.assistant.engine import sanitize, semantic_chunks, embedding, cosine, bm25_score, extract_facts, plan_tools, adapt_preferences

def test_sanitize_redacts_credentials_and_contact_data():
    value = sanitize("api_key=sk-secret abc@example.com +254 712 345 678")
    assert "sk-secret" not in value
    assert "abc@example.com" not in value
    assert "712 345 678" not in value

def test_semantic_chunks_respect_heading_boundaries():
    chunks = semantic_chunks("# Profile\n\nData engineer with Python.\n\n# Goals\n\nBuild reliable pipelines.")
    assert len(chunks) >= 2
    assert chunks[0].startswith("# Profile")
    assert any(x.startswith("# Goals") for x in chunks)

def test_hash_embeddings_are_normalized_and_deterministic():
    a = embedding("Python data engineering")
    b = embedding("Python data engineering")
    assert a == b
    assert abs(cosine(a, a) - 1.0) < 1e-5

def test_bm25_rewards_exact_terms():
    assert bm25_score("Kafka pipelines", "Kafka event pipelines") > bm25_score("Kafka pipelines", "Frontend design")

def test_fact_extraction_is_limited_to_explicit_declarations():
    facts = extract_facts("My goal is to become a data engineer.")
    assert facts and facts[0][0] == "career_goal"

def test_tool_planner_only_selects_read_only_tools():
    assert plan_tools("Show my applications") == ["application_summary"]
    assert plan_tools("Send an email to recruiter") == []

def test_feedback_updates_preference_history():
    value = adapt_preferences({}, 1, "Please be more concise")
    assert value["feedback_events"] == 1
    assert value["correction_patterns"][-1] == "Please be more concise"
