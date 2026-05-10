"""Typed planning models for the upstream scenario-honing workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whittle.models.case_spec import SimulationCaseSpec
from whittle.models.reports import TraceEvent

ScenarioType = Literal[
    "external_cruise",
    "attitude_transform",
    "hover_or_takeoff",
    "trim_guidance",
    "internal_flow",
    "vague_request",
    "unsupported",
]


class PhysicsEnvelope(BaseModel):
    """Machine-checkable limits for the early Whittle CFD demo."""

    name: str = "legacy_box_quadcopter_v0"
    default_cruise_velocity_mps: float = 5.0
    min_reference_velocity_mps: float = 0.5
    typical_max_reference_velocity_mps: float = 20.0
    hard_max_reference_velocity_mps: float = 80.0
    default_mrf_omega_rad_s: float = 1000.0
    hard_max_mrf_omega_rad_s: float = 5000.0
    max_attitude_angle_deg: float = 30.0
    supported_rotor_models: list[str] = Field(default_factory=lambda: ["none", "mrf"])
    supported_geometry_presets: list[str] = Field(default_factory=lambda: ["legacy-box"])
    notes: list[str] = Field(default_factory=list)


class ScenarioPlan(BaseModel):
    """Output of the deterministic pre-agent planning layer."""

    user_request: str
    scenario_type: ScenarioType
    spec: SimulationCaseSpec | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    trace_events: list[TraceEvent] = Field(default_factory=list)
