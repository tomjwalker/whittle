"""Human-reviewable setup report models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from whittle.models.case_spec import SimulationCaseSpec


class TraceEvent(BaseModel):
    """Visible engineering trace event, not hidden model reasoning."""

    event_type: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class CaseSetupReport(BaseModel):
    """Reviewable report returned by deterministic tools or future agents."""

    case_name: str
    spec: SimulationCaseSpec
    files_written: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    can_run: bool
    why_not_run: str | None = None
    recommended_next_steps: list[str] = Field(default_factory=list)
    trace_events: list[TraceEvent] = Field(default_factory=list)
    validation_checks: list[str] = Field(default_factory=list)

