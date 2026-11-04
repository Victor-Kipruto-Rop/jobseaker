"""Bounded multi-step orchestration with a strict read-only capability registry."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

READ_ONLY_TOOLS = frozenset({"application_summary", "interview_summary", "candidate_profile", "job_recommendations"})
MAX_STEPS = 4
MAX_TOOL_RESULT_CHARS = 6000

@dataclass
class AgentStep:
    name: str
    status: str = "planned"
    attempts: int = 0
    result: Any = None
    error: str | None = None

@dataclass
class AgentPlan:
    goal: str
    steps: list[AgentStep] = field(default_factory=list)

    @property
    def tool_names(self) -> list[str]:
        return [step.name for step in self.steps]

def plan_agent_steps(query: str) -> AgentPlan:
    """Decompose common career workflows into ordered, read-only evidence retrieval."""
    q = (query or "").casefold()
    selected: list[str] = []

    def add(*names: str) -> None:
        for name in names:
            if name in READ_ONLY_TOOLS and name not in selected and len(selected) < MAX_STEPS:
                selected.append(name)

    if any(term in q for term in ("career overview", "career health", "how am i doing", "overall progress")):
        add("candidate_profile", "application_summary", "interview_summary", "job_recommendations")
    elif any(term in q for term in ("compare", "gap analysis", "skill gap", "match my", "suitable", "fit for")):
        add("candidate_profile", "job_recommendations", "application_summary")
    elif any(term in q for term in ("interview prep", "prepare for interview", "upcoming interview", "interview preparation")):
        add("candidate_profile", "interview_summary", "application_summary")
    else:
        if any(term in q for term in ("my applications", "application status", "applications", "pipeline", "applied")):
            add("application_summary")
        if any(term in q for term in ("interview", "interviews", "schedule")):
            add("interview_summary")
        if any(term in q for term in ("my profile", "my resume", "my cv", "my skills", "experience", "profile")):
            add("candidate_profile")
        if any(term in q for term in ("job", "jobs", "opportunities", "recommend")):
            add("job_recommendations")
    return AgentPlan((query or "")[:500], [AgentStep(name) for name in selected])

def execute_plan(plan: AgentPlan, tools: dict[str, Callable[[], Any]]) -> AgentPlan:
    """Run only allowlisted read-only tools with bounded retries and output size."""
    for step in plan.steps[:MAX_STEPS]:
        if step.name not in READ_ONLY_TOOLS or step.name not in tools:
            step.status, step.error = "rejected", "Tool is not in the read-only registry."
            continue
        for attempt in range(2):
            step.attempts += 1
            try:
                result = tools[step.name]()
                if isinstance(result, str):
                    step.result = result[:MAX_TOOL_RESULT_CHARS]
                else:
                    step.result = str(result)[:MAX_TOOL_RESULT_CHARS]
                step.status = "completed"
                break
            except (TimeoutError, ConnectionError) as exc:
                step.error = type(exc).__name__
                if attempt == 1:
                    step.status = "failed"
            except Exception as exc:
                step.error = type(exc).__name__
                step.status = "failed"
                break
    return plan

def plan_trace(plan: AgentPlan) -> list[dict[str, Any]]:
    return [{"tool": step.name, "status": step.status, "attempts": step.attempts,
             "error": step.error} for step in plan.steps[:MAX_STEPS]]
