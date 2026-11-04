from packages.assistant.entity_resolution import normalize, extract_entities
from packages.assistant.orchestration import plan_agent_steps, execute_plan, plan_trace

def test_entity_normalization_handles_common_aliases():
    assert normalize("Amazon Web Services, Inc.") == "amazon web services"
    assert normalize("PostgreSQL") == "postgresql"

def test_entity_extraction_finds_skills_and_employer_mentions():
    values = extract_entities("I worked at Acme Data and use Python, PostgreSQL and Apache Kafka.")
    assert ("skill", "python") in values
    assert ("skill", "postgresql") in values
    assert ("employer", "Acme Data") in values

def test_orchestration_builds_bounded_multi_step_plan():
    plan = plan_agent_steps("Compare my CV skills with job opportunities and current applications")
    assert plan.tool_names == ["candidate_profile", "job_recommendations", "application_summary"]
    assert len(plan.steps) <= 4

def test_orchestration_executes_only_read_only_registered_tools():
    plan = plan_agent_steps("Show my applications and interview schedule")
    executed = []
    registry = {
        "application_summary": lambda: executed.append("applications") or "pipeline",
        "interview_summary": lambda: executed.append("interviews") or "schedule",
        "send_email": lambda: executed.append("email"),
    }
    result = execute_plan(plan, registry)
    assert executed == ["applications", "interviews"]
    assert all(step.status == "completed" for step in result.steps)
    assert all(item["attempts"] == 1 for item in plan_trace(result))
