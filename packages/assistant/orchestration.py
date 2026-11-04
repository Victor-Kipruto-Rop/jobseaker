"""Bounded multi-step orchestration with a strict read-only capability registry."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable

READ_ONLY_TOOLS = frozenset({"application_summary","interview_summary","candidate_profile","job_recommendations"})
MAX_STEPS = 4

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
    q = (query or "").casefold()
    selected: list[str] = []
    def add(name: str) -> None:
        if name in READ_ONLY_TOOLS and name not in selected and len(selected) < MAX_STEPS:
            selected.append(name)
    if any(x in q for x in ("compare","gap","match","suitable","fit")):
        add("candidate_profile"); add("job_recommendations"); add("application_summary")
    if any(x in q for x in ("application","pipeline","applied","status")): add("application_summary")
    if any(x in q for x in ("interview","interviews","schedule")): add("interview_summary")
    if any(x in q for x in ("profile","resume","cv","skills","experience")): add("candidate_profile")
    if any(x in q for x in ("job","jobs","opportunities","recommend")): add("job_recommendations")
    return AgentPlan((query or "")[:500], [AgentStep(name) for name in selected])

def execute_plan(plan: AgentPlan, tools: dict[str, Callable[[], Any]]) -> AgentPlan:
    for step in plan.steps:
        if step.name not in READ_ONLY_TOOLS or step.name not in tools:
            step.status, step.error = "rejected", "Tool is not in the read-only registry."
            continue
        for attempt in range(2):
            step.attempts += 1
            try:
                step.result = tools[step.name]()
                step.status = "completed"
                break
            except (TimeoutError, ConnectionError) as exc:
                step.error = type(exc).__name__
                if attempt == 1: step.status = "failed"
            except Exception as exc:
                step.error = type(exc).__name__
                step.status = "failed"
                break
    return plan

def plan_trace(plan: AgentPlan) -> list[dict[str, Any]]:
    return [{"tool": s.name, "status": s.status, "attempts": s.attempts, "error": s.error}
            for s in plan.steps]
