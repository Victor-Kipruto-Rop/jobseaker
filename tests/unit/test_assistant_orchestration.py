from packages.assistant.orchestration import execute_plan, plan_agent_steps, plan_trace

def test_career_overview_builds_bounded_multi_step_plan():
    plan = plan_agent_steps("Give me a career overview and how am I doing?")
    assert plan.tool_names == [
        "candidate_profile", "application_summary",
        "interview_summary", "job_recommendations",
    ]

def test_agent_executor_runs_only_allowlisted_tools_and_records_trace():
    plan = plan_agent_steps("Review my applications and interview schedule")
    called = []
    def applications():
        called.append("applications")
        return {"count": 3}
    result = execute_plan(plan, {
        "application_summary": applications,
        "interview_summary": lambda: "next Tuesday",
        "unexpected_tool": lambda: called.append("unsafe"),
    })
    assert called == ["applications"]
    assert all(step.status == "completed" for step in result.steps)
    assert all(item["attempts"] == 1 for item in plan_trace(result))

def test_agent_executor_bounds_tool_output_and_retries_transient_failures():
    plan = plan_agent_steps("Show my applications")
    calls = {"count": 0}
    def flaky():
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("temporary")
        return "x" * 9000
    execute_plan(plan, {"application_summary": flaky})
    assert calls["count"] == 2
    assert plan.steps[0].status == "completed"
    assert len(plan.steps[0].result) == 6000

def test_unrelated_request_does_not_schedule_tools():
    assert plan_agent_steps("Explain what a data warehouse is").steps == []
