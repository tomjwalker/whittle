"""Typed outputs for the human-facing CFD planning agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whittle.models.planning import ScenarioPlan
from whittle.models.reports import TraceEvent

PlanningAgentStatus = Literal[
    "needs_clarification",
    "ready_for_human_review",
    "ready_to_write_case",
    "out_of_scope",
    "error",
]

PlanningAgentPhase = Literal[
    "idle",
    "scope_explanation",
    "scenario_discovery",
    "clarifying",
    "coaching",
    "case_drafting",
    "human_review",
    "blocked",
    "error",
]


class PlanningAgentResponse(BaseModel):
    """Public response contract for the Whittle planning agent."""

    status: PlanningAgentStatus
    phase: PlanningAgentPhase = "idle"
    assistant_message: str
    summary: str | None = None
    scenario_plan: ScenarioPlan | None = None
    trace_events: list[TraceEvent] = Field(default_factory=list)
    model: str
    source: Literal["pydantic_ai", "deterministic_fallback"] = "pydantic_ai"
    next_actions: list[str] = Field(default_factory=list)
