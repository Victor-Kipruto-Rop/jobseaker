from packages.assistant.entity_resolution import normalize, canonicalize, extract_entities
from packages.assistant.orchestration import plan_agent_steps, execute_plan, plan_trace

def test_entity_normalization_handles_common_aliases():
    assert normalize("Amazon Web Services, Inc.") == "amazon web services"
    assert normalize("PostgreSQL") == "postgresql"
    assert canonicalize("AWS") == "amazon web services"
    assert canonicalize("psql") == "postgresql"

def test_entity_extraction_finds_skills_and_employer_mentions():
    values = extract_entities("I worked at Acme Data and use Python, PostgreSQL and Apache Kafka.")
    assert ("skill", "python") in values
    assert ("skill", "postgresql") in values
    assert ("employer", "Acme Data") in values
    aliases = extract_entities("I use AWS, psql and Py for analytics.")
    assert ("skill", "amazon web services") in aliases
    assert ("skill", "postgresql") in aliases
    assert ("skill", "python") in aliases

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


def test_orchestrator_decomposes_interview_prep_and_career_overview():
    prep = plan_agent_steps("Help me prepare for my upcoming interview")
    assert prep.tool_names == ["candidate_profile", "interview_summary", "application_summary"]
    overview = plan_agent_steps("Give me a career overview and overall progress")
    assert overview.tool_names == ["candidate_profile", "application_summary", "interview_summary", "job_recommendations"]

def test_orchestrator_rejects_unapproved_tools_and_bounds_output():
    plan = plan_agent_steps("Show my applications")
    result = execute_plan(plan, {"application_summary": lambda: "x" * 9000, "send_email": lambda: "sent"})
    assert result.steps[0].status == "completed"
    assert len(result.steps[0].result) <= 6000
    unsafe = type(plan)("unsafe", [type(plan.steps[0])("send_email")])
    execute_plan(unsafe, {"send_email": lambda: "sent"})
    assert unsafe.steps[0].status == "rejected"
