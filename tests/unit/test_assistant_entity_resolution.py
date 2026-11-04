from packages.assistant.entity_resolution import canonicalize, extract_entities, normalize

def test_skill_aliases_resolve_to_one_canonical_name():
    assert canonicalize("Py") == "python"
    assert canonicalize("Postgres") == "postgresql"
    assert canonicalize("AWS") == "amazon web services"

def test_normalization_removes_company_legal_suffixes():
    assert normalize("Acme Technologies Limited") == "acme technologies"

def test_entity_extraction_finds_supported_skills_and_roles():
    entities = extract_entities("I use Python, Kafka and SQL. My target role is Data Engineer.")
    assert ("skill", "python") in entities
    assert ("skill", "apache kafka") in entities or ("skill", "kafka") in entities
    assert any(kind == "role" and "Data Engineer" in value for kind, value in entities)
