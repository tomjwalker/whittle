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

from whittle.models.agent import PlanningAgentPhase, PlanningAgentResponse
from whittle.models.planning import ScenarioPlan
from whittle.models.reports import TraceEvent
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE, validate_physics_envelope
from whittle.tools.scenario_planner import plan_case_request

DEFAULT_AGENT_MODEL = "openai-responses:gpt-5.4-mini"
DEFAULT_AGENT_THINKING = "medium"
_SPEED_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:m/s|metres?\s+per\s+second|meters?\s+per\s+second)",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """You are Whittle, a CFD setup planning agent for an educational drone
OpenFOAM demo.

Your job is to interview the user until a physically plausible, civil, steady
incompressible drone CFD setup can be expressed as typed state.

Use the deterministic tools as the authority. Do not invent OpenFOAM file
contents, rotor coordinates, solver settings, or supported scenarios. If the
tools say a request is missing information or out of scope, ask concise
clarifying questions. Do not expose private chain-of-thought. Use visible trace
events for auditable actions such as checking the physics envelope, extracting
fields, validating the spec, or needing human review.

Current scope:
- legacy-box quadcopter geometry
- external cruise/attitude cases
- optional MRF rotor approximation
- steady incompressible simpleFoam setup
- no automatic solver execution
- no hover/takeoff/ground-effect cases yet
- no weapons, targeting, evasion, or mission optimisation

Conversation policy:
- Separate coaching from case writing. Not every user utterance should become
  a SimulationCaseSpec.
- For lay requests, explain the nearest supported workflow, then ask one
  concrete next question or offer two to four supported next actions.
- For yawing/spinning in place, explain that real yaw uses differential rotor
  torque, but mark it as a future manoeuvre workflow outside the current
  steady simpleFoam writer.
- For trim questions, offer a pitch/rotor-speed sweep, not a claimed solved
  trim state.
"""


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
        )

    try:
        agent = _build_agent(model_name, thinking_setting)
        result = await agent.run(
            _agent_prompt(user_request, case_name, conversation_history),
            model_settings={"thinking": thinking_setting},
        )
        draft = AgentPlanningDraft.model_validate(result.output)
        response = build_deterministic_agent_response(
            user_request,
            case_name=case_name,
            model=model_name,
        )
        return _apply_model_draft(response, draft, model_name)
    except Exception as exc:  # pragma: no cover - exercised only with live provider failures.
        fallback = build_deterministic_agent_response(
            user_request,
            case_name=case_name,
            model=model_name,
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
    )
    yield {"type": "complete", "response": response.model_dump(mode="json")}


def build_deterministic_agent_response(
    user_request: str,
    *,
    case_name: str = "agent_planned_case",
    model: str = DEFAULT_AGENT_MODEL,
) -> PlanningAgentResponse:
    """Wrap deterministic planning in the same contract as the model-backed agent."""

    plan = plan_case_request(user_request, case_name=case_name)
    status = _status_from_plan(plan)
    trace_events = [
        TraceEvent(
            event_type="AgentStarted",
            message="Planning agent started in deterministic fallback mode.",
            data={"case_name": case_name},
        ),
        *plan.trace_events,
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
        instructions=_SYSTEM_PROMPT,
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

        if velocity_mps <= 6:
            pitch_sweep = [0.0, 3.0, 6.0]
            omega_sweep = [800.0, 1000.0, 1200.0]
        elif velocity_mps <= 12:
            pitch_sweep = [3.0, 6.0, 9.0, 12.0]
            omega_sweep = [900.0, 1100.0, 1300.0]
        else:
            pitch_sweep = [6.0, 10.0, 14.0, 18.0]
            omega_sweep = [1100.0, 1400.0, 1700.0]
        return TrimGuidance(
            velocity_mps=velocity_mps,
            pitch_sweep_deg=pitch_sweep,
            omega_sweep_rad_s=omega_sweep,
            note=(
                "This is not a solved trim state. It is a suggested sweep to find "
                "force/moment balance in later tooling."
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
) -> str:
    return (
        f"Case name: {case_name}\n"
        f"{_format_history(conversation_history)}"
        f"User request: {user_request}\n\n"
        "First call classify_interaction. If should_draft_case is false, answer "
        "as a coaching/interview step and do not claim files are ready. If it is "
        "true, call draft_scenario_plan and then validate_scenario_request. For "
        "trim, pitch, rotor-speed, yaw-in-place, or manoeuvre coaching questions, "
        "call get_trim_guidance when useful. Return an AgentPlanningDraft. "
        "Set status to ready_for_human_review only when a SimulationCaseSpec exists "
        "and no blocking missing_information remains. If the user asks a question "
        "or needs coaching, prefer needs_clarification and ask a concrete next "
        "question instead of writing files."
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
    if any(
        term in text
        for term in (
            "yawing in place",
            "yaw in place",
            "spinning in place",
            "spin in place",
            "rotate in place",
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
                "Approximate it as 5 m/s cruise with MRF rotors.",
                "Create a pitch 10 deg MRF smoke case instead.",
                "Keep yaw-in-place as a future manoeuvre requirement.",
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
                "Propose a 10 m/s pitch/omega sweep.",
                "Write one smoke case at 10 m/s, pitch 6 deg, MRF 1100 rad/s.",
                "Explain how trim would be evaluated from forces and moments.",
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
    if status == "ready_for_human_review" and plan.spec is not None:
        return (
            f"{plan.spec.case_name}: {plan.spec.reference_velocity_mps:g} m/s, "
            f"{plan.spec.rotor_model} rotors, roll/pitch/yaw "
            f"{plan.spec.roll_angle_deg:g}/{plan.spec.pitch_angle_deg:g}/"
            f"{plan.spec.yaw_angle_deg:g} deg."
        )
    if plan.scenario_type == "trim_guidance":
        return "Trim is being handled as coaching and sweep design, not as one solved state."
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
                "I can help with the current educational drone CFD envelope: steady, "
                "incompressible, low-speed external aerodynamics for the legacy-box "
                "quadcopter.\n\n"
                "Good demo requests are: cruise at a chosen freestream speed, a fixed "
                "roll/pitch/yaw attitude case, a case with the MRF rotor approximation, "
                "or a small pitch/rotor-speed sweep to study trim. Hover, takeoff, "
                "ground effect, and true yaw-in-place manoeuvres are useful roadmap "
                "items, but they are not yet writeable as validated simpleFoam cases.\n\n"
                "Pick one scenario and a speed in m/s, then I can draft the typed case."
            )
        return (
            "That is a design goal rather than a CFD case yet. To make it demo-ready, "
            "I need to pin down the scenario: cruise, a fixed attitude case, or a "
            "rotor/downwash approximation. I also need a freestream speed in m/s and "
            "whether to include MRF rotors."
        )
    if plan.scenario_type == "trim_guidance":
        velocity = _extract_velocity_for_message(plan.user_request)
        guidance = _trim_guidance_text(velocity)
        return (
            f"For {velocity:g} m/s, I would not claim a solved trim state yet. "
            "The current system can propose a small CFD sweep and then compare "
            "forces and moments after the runs.\n\n"
            f"{guidance}\n\n"
            "The next writeable step is either one smoke case from that sweep, or a "
            "small generated suite so we can inspect lift, drag, and pitching moment."
        )
    if plan.scenario_type == "hover_or_takeoff":
        if "yaw" in plan.user_request.lower() or "spin" in plan.user_request.lower():
            return (
                "Yawing in place is a good engineering target, but it is not yet a "
                "writeable Whittle case. A real quadcopter yaws by changing the "
                "torque balance between opposite rotor pairs: one diagonal speeds up "
                "while the other slows down, ideally without changing total lift too "
                "much.\n\n"
                "The current OpenFOAM writer supports steady external cruise/attitude "
                "cases, with optional MRF rotors. For today, we can approximate this "
                "as a fixed-attitude MRF case, or keep yaw-in-place as the next "
                "manoeuvre model to implement."
            )
        return (
            "Hover/takeoff is outside the current steady external-flow writer. "
            "For today we can approximate rotor downwash in forward flight with MRF "
            "rotors, or record hover/takeoff as the next physics-envelope extension."
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
    return (
        f"I can set this up as `{plan.spec.case_name}` at "
        f"{plan.spec.reference_velocity_mps:g} m/s {rotor_text}. "
        "Please review the assumptions before writing files."
    )


def _next_actions_from_plan(plan: ScenarioPlan, status: str) -> list[str]:
    if status == "ready_for_human_review":
        return [
            "Review assumptions and warnings.",
            "Confirm whether to write the OpenFOAM case files.",
        ]
    if plan.scenario_type == "vague_request":
        return _supported_scenario_actions()
    if plan.scenario_type == "trim_guidance":
        return [
            "Write one smoke case at 10 m/s, pitch 6 deg, with MRF rotors at 1100 rad/s.",
            "Create a pitch and rotor-speed sweep for 10 m/s.",
            "Explain how to read force and moment outputs for trim.",
        ]
    if plan.scenario_type == "hover_or_takeoff":
        return [
            "Choose a yaw rate, for example 30-90 deg/s, for the future manoeuvre model.",
            "Approximate this today as 5 m/s cruise with MRF rotors.",
            "Set up pitch 10 deg at 5 m/s with MRF rotors.",
            "Add yaw-in-place as a future differential-rotor manoeuvre case.",
        ]
    if plan.clarifying_questions:
        return plan.clarifying_questions
    return ["Revise the request into the supported external drone-aero envelope."]


def _supported_scenario_actions() -> list[str]:
    return [
        "Set up cruise at 5 m/s with MRF rotors.",
        "Run pitch 10 degrees at 5 m/s with MRF rotors.",
        "Plan a 10 m/s pitch and rotor-speed sweep.",
        "Explain what is needed for yaw-in-place later.",
    ]


def _extract_velocity_for_message(text: str) -> float:
    match = _SPEED_RE.search(text)
    if match:
        return float(match.group("value"))
    return DEFAULT_PHYSICS_ENVELOPE.default_cruise_velocity_mps


def _trim_guidance_text(velocity_mps: float) -> str:
    if velocity_mps <= 6:
        return "Suggested sweep: pitch 0, 3, 6 deg crossed with 800, 1000, 1200 rad/s."
    if velocity_mps <= 12:
        return "Suggested sweep: pitch 3, 6, 9, 12 deg crossed with 900, 1100, 1300 rad/s."
    return "Suggested sweep: pitch 6, 10, 14, 18 deg crossed with 1100, 1400, 1700 rad/s."


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
