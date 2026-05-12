"""Typed planning models for the upstream scenario-honing workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whittle.models.case_spec import SimulationCaseSpec
from whittle.models.reports import TraceEvent

ScenarioType = Literal[
    "external_cruise",
    "attitude_transform",
    "static_hover_mrf",
    "motion_proxy",
    "hover_or_takeoff",
    "trim_guidance",
    "internal_flow",
    "vague_request",
    "unsupported",
]

IntentObjective = Literal[
    "external_cruise",
    "attitude_hold",
    "static_hover",
    "motion_proxy",
    "yaw_manoeuvre",
    "trim_or_performance_sweep",
    "design_exploration",
    "takeoff_or_ground_effect",
    "internal_flow",
    "unsupported",
]

IntentState = Literal[
    "proposed",
    "needs_clarification",
    "blocked",
    "ready_for_spec",
]

RotorStrategy = Literal[
    "none",
    "mrf_smoke",
    "rotor_disk_source",
    "differential_mrf_proxy",
    "performance_table_required",
    "differential_rotor_model_required",
    "unknown",
]


class ScenarioIntent(BaseModel):
    """Soft upstream intent inferred before the hard case-spec contract."""

    objective: IntentObjective
    state: IntentState
    rotor_strategy: RotorStrategy = "unknown"
    environment: Literal[
        "unbounded_external",
        "floor_or_ground",
        "internal",
        "unknown",
    ] = "unknown"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    requested_velocity_mps: float | None = None
    requested_u_mps: float | None = None
    requested_v_mps: float | None = None
    requested_w_mps: float | None = None
    requested_roll_rate_deg_s: float | None = None
    requested_pitch_rate_deg_s: float | None = None
    requested_yaw_rate_deg_s: float | None = None
    requested_roll_deg: float | None = None
    requested_pitch_deg: float | None = None
    requested_yaw_deg: float | None = None
    requested_mrf_omega_rad_s: float | None = None
    inferred_fields: dict[str, str | float | bool] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None


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
    supported_rotor_models: list[str] = Field(
        default_factory=lambda: ["none", "mrf", "rotor_disk"]
    )
    supported_geometry_presets: list[str] = Field(default_factory=lambda: ["legacy-box"])
    notes: list[str] = Field(default_factory=list)


class ScenarioPlan(BaseModel):
    """Output of the deterministic pre-agent planning layer."""

    user_request: str
    scenario_type: ScenarioType
    intent: ScenarioIntent | None = None
    spec: SimulationCaseSpec | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    trace_events: list[TraceEvent] = Field(default_factory=list)
