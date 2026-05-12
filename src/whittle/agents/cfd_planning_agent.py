"""PydanticAI-backed CFD planning agent.

The deterministic planner remains the authority for case state. The agent wraps
that planner with a conversational interface and visible trace events.
"""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from whittle.agents.prompt_loader import load_cfd_planning_prompts
from whittle.models.agent import PlanningAgentPhase, PlanningAgentResponse
from whittle.models.planning import ScenarioPlan
from whittle.models.reports import TraceEvent
from whittle.tools.performance_guidance import (
    MotionRotorCommand,
    PerformanceGuidance,
    get_cruise_performance_guidance,
)
from whittle.tools.performance_guidance import (
    get_motion_rotor_command as compute_motion_rotor_command,
)
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE, validate_physics_envelope
from whittle.tools.scenario_planner import plan_case_request

DEFAULT_AGENT_MODEL = "openai-responses:gpt-5.4-mini"
DEFAULT_AGENT_THINKING = "medium"
_SPEED_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:m/s|metres?\s+per\s+second|meters?\s+per\s+second)",
    re.IGNORECASE,
)
_ZERO_SPEED_RE = re.compile(r"(?<!\d)0(?:\.0+)?\s*m/s", re.IGNORECASE)


class AgentPlanningDraft(BaseModel):
    """Strict-schema-friendly model output for the PydanticAI agent."""

    status: Literal[
        "needs_clarification",
        "ready_for_human_review",
        "ready_to_write_case",
        "out_of_scope",
        "error",
    ]
    phase: PlanningAgentPhase = "clarifying"
    assistant_message: str
    summary: str | None = None
    next_actions: list[str] = Field(default_factory=list)


class InteractionClassification(BaseModel):
    """Lightweight intent classification for conversational planning."""

    intent: Literal[
        "capabilities_question",
        "vague_design_goal",
        "case_request",
        "trim_guidance",
        "unsupported_manoeuvre",
        "unsupported_request",
    ]
    phase: PlanningAgentPhase
    should_draft_case: bool
    message: str
    suggested_replies: list[str] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    """Compact model-visible validation summary."""

    check_count: int
    warning_count: int
    missing_count: int
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    """Prior chat message passed from the UI."""

    role: Literal["user", "assistant"]
    content: str


class TrimGuidance(BaseModel):
    """Heuristic guidance for planning a future trim/sweep workflow."""

    velocity_mps: float
    pitch_sweep_deg: list[float]
    omega_sweep_rad_s: list[float]
    note: str


async def run_planning_agent(
    user_request: str,
    *,
    case_name: str = "agent_planned_case",
    model: str | None = None,
    thinking: str | bool | None = None,
    deterministic: bool = False,
    conversation_history: list[ConversationMessage] | None = None,
    previous_plan: ScenarioPlan | None = None,
) -> PlanningAgentResponse:
    """Run the planning agent, falling back to deterministic planning when needed."""

    model_name = model or os.getenv("WHITTLE_AGENT_MODEL", DEFAULT_AGENT_MODEL)
    thinking_setting = thinking if thinking is not None else os.getenv(
        "WHITTLE_AGENT_THINKING",
        DEFAULT_AGENT_THINKING,
    )
    if deterministic or not _can_use_model(model_name):
        return build_deterministic_agent_response(
            user_request,
            case_name=case_name,
            model=model_name,
            previous_plan=previous_plan,
        )

    try:
        agent = _build_agent(model_name, thinking_setting)
        result = await agent.run(
            _agent_prompt(user_request, case_name, conversation_history, previous_plan),
            model_settings={"thinking": thinking_setting},
        )
        draft = AgentPlanningDraft.model_validate(result.output)
        response = build_deterministic_agent_response(
            user_request,
            case_name=case_name,
            model=model_name,
            previous_plan=previous_plan,
        )
        return _apply_model_draft(response, draft, model_name)
    except Exception as exc:  # pragma: no cover - exercised only with live provider failures.
        fallback = build_deterministic_agent_response(
            user_request,
            case_name=case_name,
            model=model_name,
            previous_plan=previous_plan,
        )
        fallback.status = "error"
        fallback.phase = "error"
        fallback.assistant_message = (
            "The model-backed planner failed, so I returned the deterministic planning result. "
            f"Error: {exc}"
        )
        fallback.trace_events.append(
            TraceEvent(
                event_type="AgentError",
                message="PydanticAI planner failed and deterministic fallback was used.",
                data={"error": str(exc)},
            )
        )
        return fallback


async def stream_planning_agent(
    user_request: str,
    *,
    case_name: str = "agent_planned_case",
    model: str | None = None,
    thinking: str | bool | None = None,
    deterministic: bool = False,
    conversation_history: list[ConversationMessage] | None = None,
    previous_plan: ScenarioPlan | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield NDJSON-friendly visible events for the planning UI."""

    model_name = model or os.getenv("WHITTLE_AGENT_MODEL", DEFAULT_AGENT_MODEL)
    thinking_setting = thinking if thinking is not None else os.getenv(
        "WHITTLE_AGENT_THINKING",
        DEFAULT_AGENT_THINKING,
    )
    yield _stream_trace(
        "RequestReceived",
        "Planning request received.",
        {"case_name": case_name, "model": model_name},
    )

    if deterministic or not _can_use_model(model_name):
        yield _stream_trace(
            "DeterministicFallback",
            "No usable model credentials found; deterministic planner is running.",
            {"model": model_name},
        )
        response = build_deterministic_agent_response(
            user_request,
            case_name=case_name,
            model=model_name,
            previous_plan=previous_plan,
        )
        yield {"type": "complete", "response": response.model_dump(mode="json")}
        return

    yield _stream_trace(
        "AgentStarted",
        "PydanticAI planner started with deterministic tools available.",
        {"model": model_name},
    )
    response = await run_planning_agent(
        user_request,
        case_name=case_name,
        model=model_name,
        thinking=thinking_setting,
        deterministic=False,
        conversation_history=conversation_history,
        previous_plan=previous_plan,
    )
    yield {"type": "complete", "response": response.model_dump(mode="json")}


def build_deterministic_agent_response(
    user_request: str,
    *,
    case_name: str = "agent_planned_case",
    model: str = DEFAULT_AGENT_MODEL,
    previous_plan: ScenarioPlan | None = None,
) -> PlanningAgentResponse:
    """Wrap deterministic planning in the same contract as the model-backed agent."""

    contextual_request = _contextualise_request(user_request, previous_plan)
    plan = plan_case_request(contextual_request, case_name=case_name)
    if contextual_request != user_request:
        plan.user_request = user_request
        plan.trace_events.insert(
            1,
            TraceEvent(
                event_type="PreviousPlanApplied",
                message="Previous structured plan was used to interpret a follow-up request.",
                data={
                    "original_request": user_request,
                    "contextual_request": contextual_request,
                },
            ),
        )
    status = _status_from_plan(plan)
    trace_events = [
        TraceEvent(
            event_type="AgentStarted",
            message="Planning agent started in deterministic fallback mode.",
            data={"case_name": case_name},
        ),
        *plan.trace_events,
        *_performance_guidance_trace_events(plan),
        _terminal_trace_event(status),
    ]
    return PlanningAgentResponse(
        status=status,
        phase=_phase_from_plan(plan, status),
        assistant_message=_message_from_plan(plan, status),
        summary=_summary_from_plan(plan, status),
        scenario_plan=plan,
        trace_events=trace_events,
        model=model,
        source="deterministic_fallback",
        next_actions=_next_actions_from_plan(plan, status),
    )


def _build_agent(model: str, thinking: str | bool):
    try:
        from pydantic_ai import Agent
    except ImportError as exc:  # pragma: no cover - dependency is installed in normal agent extra.
        raise RuntimeError(
            "PydanticAI is not installed. Run `uv sync` after the latest pyproject update."
        ) from exc

    agent = Agent(
        model,
        instructions=load_cfd_planning_prompts().system_prompt,
        output_type=AgentPlanningDraft,
        model_settings={"thinking": thinking},
    )

    @agent.tool_plain
    def classify_interaction(user_request: str) -> InteractionClassification:
        """Classify whether the user is asking for coaching, scope, or a case draft."""

        return _classify_interaction(user_request)

    @agent.tool_plain
    def get_physics_envelope() -> dict[str, Any]:
        """Return the current machine-checkable CFD physics envelope."""

        return DEFAULT_PHYSICS_ENVELOPE.model_dump(mode="json")

    @agent.tool_plain
    def get_performance_guidance(
        velocity_mps: float = 5.0,
        yaw_rate_deg_s: float | None = None,
    ) -> PerformanceGuidance:
        """Return heuristic pitch and signed rotor-speed defaults for lay planning.

        Use this before giving numeric recommendations for cruise speed, pitch,
        trim, MRF omega, or future yaw manoeuvre proxies. The values are
        transparent table/interpolation guidance, not solved trim.
        """

        return get_cruise_performance_guidance(
            velocity_mps,
            yaw_rate_deg_s=yaw_rate_deg_s,
        )

    @agent.tool_plain
    def get_motion_rotor_command(
        u_mps: float = 0.0,
        v_mps: float = 0.0,
        w_mps: float = 0.0,
        roll_deg: float = 0.0,
        pitch_deg: float | None = None,
        yaw_deg: float = 0.0,
        roll_rate_deg_s: float = 0.0,
        pitch_rate_deg_s: float = 0.0,
        yaw_rate_deg_s: float = 0.0,
    ) -> MotionRotorCommand:
        """Return a bounded heuristic per-rotor command for bespoke manoeuvres.

        Use this when the user asks about yawing, rolling, pitching, spinning,
        side-slip, vertical motion, or combined attitude-rate manoeuvres. The
        returned signed MRF rotor speeds are a steady CFD proxy, not direct
        body angular-rate simulation or solved trim.
        """

        return compute_motion_rotor_command(
            u_mps=u_mps,
            v_mps=v_mps,
            w_mps=w_mps,
            roll_deg=roll_deg,
            pitch_deg=pitch_deg,
            yaw_deg=yaw_deg,
            roll_rate_deg_s=roll_rate_deg_s,
            pitch_rate_deg_s=pitch_rate_deg_s,
            yaw_rate_deg_s=yaw_rate_deg_s,
        )

    @agent.tool_plain
    def draft_scenario_plan(
        user_request: str,
        case_name: str = "agent_planned_case",
    ) -> dict[str, Any]:
        """Run the deterministic planner for a natural-language CFD request."""

        plan = plan_case_request(user_request, case_name=case_name)
        return plan.model_dump(mode="json")

    @agent.tool_plain
    def validate_scenario_request(
        user_request: str,
        case_name: str = "agent_planned_case",
    ) -> ValidationSummary:
        """Validate a drafted natural-language request against the physics envelope."""

        plan = plan_case_request(user_request, case_name=case_name)
        if plan.spec is None:
            return ValidationSummary(
                check_count=0,
                warning_count=len(plan.warnings),
                missing_count=len(plan.missing_information),
                warnings=plan.warnings,
                missing_information=plan.missing_information,
            )
        checks, warnings, missing = validate_physics_envelope(plan.spec, DEFAULT_PHYSICS_ENVELOPE)
        return ValidationSummary(
            check_count=len(checks),
            warning_count=len(warnings),
            missing_count=len(missing),
            warnings=warnings,
            missing_information=missing,
        )

    @agent.tool_plain
    def get_trim_guidance(velocity_mps: float = 10.0) -> TrimGuidance:
        """Return conservative educational sweep guidance for a future trim workflow."""

        guidance = get_cruise_performance_guidance(velocity_mps)
        return TrimGuidance(
            velocity_mps=velocity_mps,
            pitch_sweep_deg=guidance.pitch_sweep_deg,
            omega_sweep_rad_s=guidance.omega_sweep_rad_s,
            note=(
                "This is not a solved trim state. It is table/interpolation guidance "
                "for a future force/moment sweep."
            ),
        )

    return agent


def _can_use_model(model: str) -> bool:
    if model.startswith(("test:", "function:", "fallback:")):
        return True
    if model.startswith(("openai:", "openai-responses:")):
        return bool(os.getenv("OPENAI_API_KEY"))
    return True


def _agent_prompt(
    user_request: str,
    case_name: str,
    conversation_history: list[ConversationMessage] | None = None,
    previous_plan: ScenarioPlan | None = None,
) -> str:
    runtime_prompt = load_cfd_planning_prompts().runtime_prompt
    return (
        f"Case name: {case_name}\n"
        f"{_format_history(conversation_history)}"
        f"{_format_previous_plan(previous_plan)}"
        f"User request: {user_request}\n\n"
        f"{runtime_prompt}"
    )


def _format_history(history: list[ConversationMessage] | None) -> str:
    if not history:
        return ""
    recent = history[-8:]
    lines = ["Recent conversation:"]
    for item in recent:
        content = item.content.strip()
        if content:
            lines.append(f"{item.role}: {content}")
    return "\n".join(lines) + "\n\n"


def _format_previous_plan(plan: ScenarioPlan | None) -> str:
    if plan is None:
        return ""
    fields = [
        f"scenario_type={plan.scenario_type}",
        f"status_intent={plan.intent.state if plan.intent else 'unknown'}",
        f"objective={plan.intent.objective if plan.intent else 'unknown'}",
    ]
    if plan.spec is not None:
        fields.extend(
            [
                f"velocity_mps={plan.spec.reference_velocity_mps:g}",
                f"rotor_model={plan.spec.rotor_model}",
                f"roll_deg={plan.spec.roll_angle_deg:g}",
                f"pitch_deg={plan.spec.pitch_angle_deg:g}",
                f"yaw_deg={plan.spec.yaw_angle_deg:g}",
            ]
        )
    return "Previous structured plan: " + ", ".join(fields) + "\n\n"


def _contextualise_request(
    user_request: str,
    previous_plan: ScenarioPlan | None,
) -> str:
    """Add prior typed state to simple follow-up edits for deterministic fallback."""

    if previous_plan is None or previous_plan.spec is None:
        return user_request

    text = user_request.lower()
    if any(
        term in text
        for term in (
            "what scenarios",
            "what can you help",
            "what do you support",
            "what are the supported",
        )
    ):
        return user_request

    modification_terms = (
        "make it",
        "faster",
        "slower",
        "same",
        "keep",
        "increase",
        "decrease",
        "instead",
        "now",
        "that",
        "this",
        "also",
        "what kind of pitch",
        "rotor speeds",
    )
    if not any(term in text for term in modification_terms):
        return user_request

    spec = previous_plan.spec
    additions: list[str] = []
    if _SPEED_RE.search(text) is None:
        additions.append(f"{spec.reference_velocity_mps:g} m/s")
    if not any(term in text for term in ("prop", "rotor", "mrf", "downwash", "swirl")):
        additions.append("with MRF rotors" if spec.rotor_model == "mrf" else "without rotors")
    if not any(axis in text for axis in ("roll", "pitch", "yaw")) and any(
        value != 0
        for value in (
            spec.roll_angle_deg,
            spec.pitch_angle_deg,
            spec.yaw_angle_deg,
        )
    ):
        additions.append(
            "roll "
            f"{spec.roll_angle_deg:g} deg, pitch {spec.pitch_angle_deg:g} deg, "
            f"yaw {spec.yaw_angle_deg:g} deg"
        )
    if not additions:
        return user_request
    return f"{user_request} Context from previous accepted draft: {', '.join(additions)}."


def _normalise_response(response: PlanningAgentResponse, model: str) -> PlanningAgentResponse:
    response.model = response.model or model
    response.source = "pydantic_ai"
    if response.scenario_plan and not response.trace_events:
        response.trace_events = response.scenario_plan.trace_events
    return response


def _apply_model_draft(
    response: PlanningAgentResponse,
    draft: AgentPlanningDraft,
    model: str,
) -> PlanningAgentResponse:
    response.model = model
    response.source = "pydantic_ai"
    over_ready_without_spec = (
        response.scenario_plan is not None
        and response.scenario_plan.spec is None
        and draft.status in {"ready_for_human_review", "ready_to_write_case"}
    )
    if over_ready_without_spec:
        response.status = _status_from_plan(response.scenario_plan)
    else:
        response.status = draft.status
    if over_ready_without_spec and response.scenario_plan is not None:
        response.phase = _phase_from_plan(response.scenario_plan, response.status)
    else:
        response.phase = draft.phase
    response.assistant_message = draft.assistant_message
    response.summary = draft.summary or response.summary
    for event in response.trace_events:
        if event.event_type == "AgentStarted":
            event.event_type = "DeterministicDraftCreated"
            event.message = "Deterministic planner drafted case state for model review."
            event.data = {"model": model}
    if draft.next_actions:
        response.next_actions = draft.next_actions
    response.trace_events.append(
        TraceEvent(
            event_type="AgentOutputPlanned",
            message="Model reviewed the deterministic draft and produced a response.",
            data={"status": draft.status},
        )
    )
    return response


def _classify_interaction(user_request: str) -> InteractionClassification:
    text = user_request.lower()
    if any(
        term in text
        for term in (
            "what scenarios",
            "what can you help",
            "what can whittle",
            "what are the supported",
            "what do you support",
        )
    ):
        return InteractionClassification(
            intent="capabilities_question",
            phase="scope_explanation",
            should_draft_case=False,
            message="The user is asking what the current CFD envelope can support.",
            suggested_replies=_supported_scenario_actions(),
        )
    if any(term in text for term in ("weapon", "target", "evasion", "payload attack")):
        return InteractionClassification(
            intent="unsupported_request",
            phase="blocked",
            should_draft_case=False,
            message="The request is outside the civil educational CFD scope.",
            suggested_replies=["Reframe this as civil external drone aerodynamics."],
        )
    if _is_static_hover_text(text):
        return InteractionClassification(
            intent="case_request",
            phase="case_drafting",
            should_draft_case=True,
            message="The user is asking for a static zero-freestream MRF hover smoke case.",
            suggested_replies=[],
        )
    if _is_motion_proxy_text(text):
        return InteractionClassification(
            intent="case_request",
            phase="case_drafting",
            should_draft_case=True,
            message=(
                "The user is asking for a bespoke motion proxy that can be "
                "represented with differential MRF rotor speeds."
            ),
            suggested_replies=[],
        )
    if any(
        term in text
        for term in (
            "hover",
            "takeoff",
            "take-off",
            "landing",
        )
    ):
        return InteractionClassification(
            intent="unsupported_manoeuvre",
            phase="coaching",
            should_draft_case=False,
            message="The user is asking for a manoeuvre outside the current steady writer.",
            suggested_replies=[
                "Capture yaw as a future differential-rotor requirement.",
                "Write a supported 5 m/s MRF cruise baseline instead.",
            ],
        )
    if any(
        term in text
        for term in (
            "what kind of pitch",
            "what pitch",
            "which pitch",
            "rotor speed",
            "rotor speeds",
            "trim",
        )
    ):
        return InteractionClassification(
            intent="trim_guidance",
            phase="coaching",
            should_draft_case=False,
            message="The user is asking for trim guidance rather than one case file.",
            suggested_replies=[
                "Write one expert-default MRF baseline case.",
                "Record a future pitch/omega trim-sweep requirement.",
            ],
        )
    if any(term in text for term in ("make it aero", "more aerodynamic", "better aerodynamic")):
        return InteractionClassification(
            intent="vague_design_goal",
            phase="scenario_discovery",
            should_draft_case=False,
            message="The user has a design objective but not a CFD case scenario yet.",
            suggested_replies=_supported_scenario_actions(),
        )
    return InteractionClassification(
        intent="case_request",
        phase="case_drafting",
        should_draft_case=True,
        message="The user appears to be asking for a draftable CFD case.",
        suggested_replies=[],
    )


def _status_from_plan(plan: ScenarioPlan):
    if plan.scenario_type in {"unsupported", "internal_flow", "hover_or_takeoff"}:
        return "out_of_scope"
    if plan.missing_information or plan.clarifying_questions or plan.spec is None:
        return "needs_clarification"
    return "ready_for_human_review"


def _phase_from_plan(plan: ScenarioPlan, status: str) -> PlanningAgentPhase:
    if status == "ready_for_human_review":
        return "human_review"
    if status == "error":
        return "error"
    if status == "out_of_scope":
        if plan.scenario_type == "hover_or_takeoff":
            return "coaching"
        return "blocked"
    if plan.scenario_type == "trim_guidance":
        return "coaching"
    if plan.scenario_type == "vague_request":
        if any(
            term in plan.user_request.lower()
            for term in ("what scenarios", "what can you help", "what do you support")
        ):
            return "scope_explanation"
        return "scenario_discovery"
    if plan.spec is not None:
        return "clarifying"
    return "clarifying"


def _summary_from_plan(plan: ScenarioPlan, status: str) -> str:
    if plan.scenario_type == "motion_proxy":
        return (
            "Differential-MRF motion proxy: steady case with per-rotor speed "
            "deltas, not a direct angular-rate simulation."
        )
    if status == "ready_for_human_review" and plan.spec is not None:
        return (
            f"{plan.spec.case_name}: {plan.spec.reference_velocity_mps:g} m/s, "
            f"{plan.spec.rotor_model} rotors, roll/pitch/yaw "
            f"{plan.spec.roll_angle_deg:g}/{plan.spec.pitch_angle_deg:g}/"
            f"{plan.spec.yaw_angle_deg:g} deg."
        )
    if plan.scenario_type == "trim_guidance":
        return "Trim is being handled as coaching and sweep design, not as one solved state."
    if plan.scenario_type == "static_hover_mrf":
        return (
            "Static hover MRF smoke case: zero freestream, zero/default attitude, "
            "spinning rotors, no floor or trim claim."
        )
    if plan.scenario_type == "hover_or_takeoff":
        return (
            "Manoeuvre request captured, but not yet writeable in the steady "
            "simpleFoam envelope."
        )
    if plan.scenario_type == "vague_request":
        return "Need scenario, speed, and rotor modelling choice before case writing."
    return "Planning request needs more information before case writing."


def _message_from_plan(plan: ScenarioPlan, status: str) -> str:
    if plan.scenario_type == "vague_request":
        if any(
            term in plan.user_request.lower()
            for term in (
                "what scenarios",
                "what can you help",
                "what do you support",
                "what are the supported",
            )
        ):
            return (
                "I can help with one strong demo path today: a steady low-speed drone "
                "CFD case for the legacy quadcopter, usually with the MRF rotor "
                "approximation switched on so the props have a cheap spinning-zone "
                "model.\n\n"
                "My recommended layperson default is a 5 m/s cruise case with MRF "
                "rotors at the heuristic 1000 rad/s baseline. The other useful demo is "
                "a static 0 m/s hover smoke case with the same rotors, clearly labelled "
                "as an approximation rather than validated hover trim."
            )
        return (
            "That is a design goal rather than a CFD case yet. I would turn it into a "
            "baseline cruise/downwash study first: 5 m/s, MRF rotors, then inspect "
            "pressure and velocity fields. If that is too slow or too fast, give me "
            "one target speed and I will update the typed case."
        )
    if plan.scenario_type == "trim_guidance":
        velocity = _extract_velocity_for_message(plan.user_request)
        guidance = get_cruise_performance_guidance(velocity)
        rotor_summary = _rotor_speed_summary(guidance.baseline_rotor_speeds_rad_s)
        return (
            f"For {velocity:g} m/s, I would use an expert-default baseline rather "
            f"than making you pick numbers: pitch about {guidance.recommended_pitch_deg:g} deg "
            f"and shared MRF magnitude about {guidance.baseline_omega_rad_s:g} rad/s. "
            f"Signed rotor speeds would be {rotor_summary}.\n\n"
            "This is a heuristic starting point from the performance table, not a "
            "solved trim result. The disciplined next step is either to write that "
            "one baseline case, or record a future trim sweep that varies pitch and "
            f"omega over {guidance.pitch_sweep_deg} deg and "
            f"{guidance.omega_sweep_rad_s} rad/s."
        )
    if plan.scenario_type == "hover_or_takeoff":
        if "yaw" in plan.user_request.lower() or "spin" in plan.user_request.lower():
            yaw_rate = plan.intent.requested_yaw_rate_deg_s if plan.intent else None
            if yaw_rate is None and "slow" in plan.user_request.lower():
                yaw_rate = 30.0
            guidance = get_cruise_performance_guidance(
                DEFAULT_PHYSICS_ENVELOPE.default_cruise_velocity_mps,
                yaw_rate_deg_s=yaw_rate,
            )
            proxy_text = ""
            if guidance.yaw_proxy_rotor_speeds_rad_s is not None and yaw_rate is not None:
                proxy_text = (
                    "\n\n"
                    f"For a future slow-yaw proxy, I would start around {yaw_rate:g} deg/s "
                    "and perturb the opposite rotor pairs like this: "
                    f"{_rotor_speed_summary(guidance.yaw_proxy_rotor_speeds_rad_s)}."
                )
            return (
                "Yawing in place is the right physical concept, but it crosses the "
                "current contract boundary. A real quadcopter yaws by changing rotor "
                "torque balance between opposite pairs; the current steady simpleFoam "
                "writer cannot impose yaw_dot directly."
                f"{proxy_text}\n\n"
                "For a writeable case today, I would lock a 5 m/s MRF cruise baseline. "
                "For the roadmap, I would record yaw-in-place as a differential-rotor "
                "manoeuvre requirement."
            )
        return (
            "Hover/takeoff is outside the current steady external-flow writer. "
            "For today we can approximate rotor downwash in forward flight with MRF "
            "rotors, or record hover/takeoff as the next physics-envelope extension."
        )
    if plan.scenario_type == "static_hover_mrf" and plan.spec is not None:
        max_omega = max((abs(zone.omega_rad_s) for zone in plan.spec.mrf_zones), default=0.0)
        return (
            f"I can draft this as `{plan.spec.case_name}`: a steady static MRF hover "
            f"smoke case with 0 m/s freestream, roll/pitch/yaw "
            f"{plan.spec.roll_angle_deg:g}/{plan.spec.pitch_angle_deg:g}/"
            f"{plan.spec.yaw_angle_deg:g} deg, and rotor MRF speed "
            f"{max_omega:g} rad/s.\n\n"
            "This is intentionally labelled as a smoke approximation. It can show "
            "rotor-driven flow/downwash around the legacy quadcopter, but it is not "
            "a validated hover trim, takeoff transient, or floor/ground-effect case."
        )
    if plan.scenario_type == "motion_proxy" and plan.spec is not None:
        return (
            f"I can draft this as `{plan.spec.case_name}`: a steady differential-MRF "
            f"motion proxy with u={plan.spec.reference_velocity_mps:g} m/s and "
            f"roll/pitch/yaw attitude {plan.spec.roll_angle_deg:g}/"
            f"{plan.spec.pitch_angle_deg:g}/{plan.spec.yaw_angle_deg:g} deg. "
            f"Rotor speeds: {_mrf_speed_summary_from_spec(plan.spec.mrf_zones)}.\n\n"
            "This is useful for interview/demo purposes because it turns a lay "
            "manoeuvre request into a typed, inspectable CFD proxy. It is not a "
            "solved flight-dynamics controller, and simpleFoam is not imposing "
            "body roll_dot/pitch_dot/yaw_dot directly."
        )
    if status == "out_of_scope":
        question = f" {plan.clarifying_questions[0]}" if plan.clarifying_questions else ""
        return f"This request is outside the current Whittle physics envelope.{question}"
    if status == "needs_clarification":
        if plan.clarifying_questions:
            return plan.clarifying_questions[0]
        return "I need one or two more details before this can become a case spec."
    assert plan.spec is not None
    rotor_text = "with MRF rotors" if plan.spec.rotor_model == "mrf" else "without rotor forcing"
    rotor_detail = ""
    if plan.spec.rotor_model == "mrf":
        rotor_detail = f" Rotor speeds: {_mrf_speed_summary_from_spec(plan.spec.mrf_zones)}."
    return (
        f"I can set this up as `{plan.spec.case_name}` at "
        f"{plan.spec.reference_velocity_mps:g} m/s {rotor_text}."
        f"{rotor_detail} "
        "Please review the assumptions before writing files."
    )


def _next_actions_from_plan(plan: ScenarioPlan, status: str) -> list[str]:
    if plan.scenario_type == "motion_proxy":
        return [
            "Write this differential-MRF proxy case.",
            "Revise the requested rates or freestream speed first.",
        ]
    if status == "ready_for_human_review":
        return [
            "Write this baseline OpenFOAM case.",
            "Revise speed, attitude, or rotor speed first.",
        ]
    if plan.scenario_type == "vague_request":
        return _supported_scenario_actions()
    if plan.scenario_type == "static_hover_mrf":
        return [
            "Review the zero-freestream MRF assumptions.",
            "Confirm whether to write the static hover smoke case.",
        ]
    if plan.scenario_type == "trim_guidance":
        velocity = _extract_velocity_for_message(plan.user_request)
        guidance = get_cruise_performance_guidance(velocity)
        return [
            (
                f"Lock one baseline: {velocity:g} m/s, pitch "
                f"{guidance.recommended_pitch_deg:g} deg, MRF "
                f"{guidance.baseline_omega_rad_s:g} rad/s."
            ),
            "Record a future pitch/omega trim-sweep requirement.",
        ]
    if plan.scenario_type == "hover_or_takeoff":
        return [
            "Write a supported 5 m/s MRF cruise baseline.",
            "Record yaw-in-place as a future differential-rotor manoeuvre case.",
        ]
    if plan.clarifying_questions:
        return plan.clarifying_questions
    return ["Revise the request into the supported external drone-aero envelope."]


def _supported_scenario_actions() -> list[str]:
    return [
        "Set up cruise at 5 m/s with MRF rotors.",
        "Set up a slow yaw-in-place differential-MRF proxy.",
    ]


def _extract_velocity_for_message(text: str) -> float:
    match = _SPEED_RE.search(text)
    if match:
        return float(match.group("value"))
    return DEFAULT_PHYSICS_ENVELOPE.default_cruise_velocity_mps


def _trim_guidance_text(velocity_mps: float) -> str:
    guidance = get_cruise_performance_guidance(velocity_mps)
    return (
        f"Suggested sweep: pitch {guidance.pitch_sweep_deg} deg crossed with "
        f"{guidance.omega_sweep_rad_s} rad/s."
    )


def _rotor_speed_summary(rotors: Any) -> str:
    return (
        f"FL {rotors.propeller_fl_rad_s:g}, FR {rotors.propeller_fr_rad_s:g}, "
        f"RL/BL {rotors.propeller_bl_rad_s:g}, RR/BR {rotors.propeller_br_rad_s:g} rad/s"
    )


def _mrf_speed_summary_from_spec(zones: list[Any]) -> str:
    by_patch = {zone.source_patch: zone.omega_rad_s for zone in zones}
    if not by_patch:
        return "none"
    return (
        f"FL {by_patch.get('propeller_fl', 0.0):g}, "
        f"FR {by_patch.get('propeller_fr', 0.0):g}, "
        f"RL/BL {by_patch.get('propeller_bl', 0.0):g}, "
        f"RR/BR {by_patch.get('propeller_br', 0.0):g} rad/s"
    )


def _is_static_hover_text(text: str) -> bool:
    if _requires_floor_or_ground(text):
        return False
    if any(term in text for term in ("takeoff", "take-off", "landing")):
        return False
    if any(term in text for term in ("yawing in place", "yaw in place", "spin", "rotate")):
        return False
    return any(
        term in text
        for term in (
            "hover",
            "hover-in-place",
            "hover in place",
            "zero freestream",
            "0 freestream",
            "0 onset",
        )
    ) or bool(_ZERO_SPEED_RE.search(text))


def _is_motion_proxy_text(text: str) -> bool:
    if _requires_floor_or_ground(text):
        return False
    if any(term in text for term in ("takeoff", "take-off", "landing")):
        return False
    return any(
        term in text
        for term in (
            "yawing in place",
            "yaw in place",
            "spinning in place",
            "spin in place",
            "rotate in place",
            "rolling in place",
            "roll in place",
            "pitching in place",
            "pitch in place",
            "deg/s",
            "degrees per second",
            "slow yaw",
            "slowly yaw",
            "slow roll",
            "slowly roll",
            "slow pitch",
            "slowly pitch",
        )
    )


def _requires_floor_or_ground(text: str) -> bool:
    if not any(term in text for term in ("floor", "ground", "ground-effect", "ground effect")):
        return False
    negated_terms = (
        "no floor",
        "without floor",
        "no need for the floor",
        "no need for a floor",
        "no ground",
        "without ground",
        "no ground effect",
        "no ground-effect",
    )
    return not any(term in text for term in negated_terms)


def _terminal_trace_event(status: str) -> TraceEvent:
    if status == "ready_for_human_review":
        return TraceEvent(
            event_type="HumanReviewNeeded",
            message="Planner output needs human review before writing files.",
            data={"status": status},
        )
    if status == "needs_clarification":
        return TraceEvent(
            event_type="ClarificationNeeded",
            message="Planner needs more information before files can be written.",
            data={"status": status},
        )
    return TraceEvent(
        event_type="RequestOutOfScope",
        message="Planner classified the request outside the current physics envelope.",
        data={"status": status},
    )


def _performance_guidance_trace_events(plan: ScenarioPlan) -> list[TraceEvent]:
    if plan.scenario_type == "trim_guidance":
        velocity = _extract_velocity_for_message(plan.user_request)
        guidance = get_cruise_performance_guidance(velocity)
        return [
            TraceEvent(
                event_type="PerformanceGuidanceRun",
                message="Heuristic pitch and rotor-speed guidance was generated.",
                data=guidance.model_dump(mode="json"),
            )
        ]
    if plan.scenario_type == "hover_or_takeoff" and (
        "yaw" in plan.user_request.lower() or "spin" in plan.user_request.lower()
    ):
        yaw_rate = plan.intent.requested_yaw_rate_deg_s if plan.intent else None
        if yaw_rate is None and "slow" in plan.user_request.lower():
            yaw_rate = 30.0
        guidance = get_cruise_performance_guidance(
            DEFAULT_PHYSICS_ENVELOPE.default_cruise_velocity_mps,
            yaw_rate_deg_s=yaw_rate,
        )
        return [
            TraceEvent(
                event_type="PerformanceGuidanceRun",
                message="Future differential-rotor yaw proxy guidance was generated.",
                data=guidance.model_dump(mode="json"),
            )
        ]
    return []


def _stream_trace(
    event_type: str,
    message: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "trace",
        "event": TraceEvent(
            event_type=event_type,
            message=message,
            data=data or {},
        ).model_dump(mode="json"),
    }


def _serialise_pydantic_event(event: Any) -> dict[str, Any] | None:
    event_name = type(event).__name__
    if event_name == "FunctionToolCallEvent":
        tool_name = _tool_name_from_event(event)
        return _stream_trace(
            "ToolCallStarted",
            f"Calling tool `{tool_name or 'unknown'}`.",
            {"event": event_name, "tool_name": tool_name},
        )
    if event_name == "FunctionToolResultEvent":
        tool_name = _tool_name_from_event(event)
        return _stream_trace(
            "ToolCallCompleted",
            f"Tool `{tool_name or 'unknown'}` returned.",
            {"event": event_name, "tool_name": tool_name},
        )
    if event_name == "FinalResultEvent":
        return _stream_trace("AgentOutputPlanned", "Agent produced a typed planning response.")
    if event_name == "PartDeltaEvent":
        delta = _event_field(event, "delta")
        delta_name = type(delta).__name__
        if delta_name == "TextPartDelta":
            text = _event_field(delta, "content_delta") or ""
            if text:
                return {"type": "assistant_delta", "delta": text}
        if delta_name == "ThinkingPartDelta":
            return _stream_trace(
                "ReasoningUpdate",
                "Model reasoning update received; raw hidden reasoning is not displayed.",
            )
    return None


def _tool_name_from_event(event: Any) -> Any:
    return _event_field(event, "tool_name") or _event_field(
        _event_field(event, "part"),
        "tool_name",
    )


def _event_field(event: Any, name: str) -> Any:
    if event is None:
        return None
    if hasattr(event, name):
        return getattr(event, name)
    if isinstance(event, dict):
        return event.get(name)
    return None
