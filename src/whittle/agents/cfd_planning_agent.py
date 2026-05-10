"""PydanticAI-backed CFD planning agent.

The deterministic planner remains the authority for case state. The agent wraps
that planner with a conversational interface and visible trace events.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any, Literal

from pydantic import BaseModel, Field

from whittle.models.agent import PlanningAgentResponse
from whittle.models.planning import ScenarioPlan
from whittle.models.reports import TraceEvent
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE, validate_physics_envelope
from whittle.tools.scenario_planner import plan_case_request

DEFAULT_AGENT_MODEL = "openai-responses:gpt-5.4-mini"
DEFAULT_AGENT_THINKING = "medium"

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
    assistant_message: str
    next_actions: list[str] = Field(default_factory=list)


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
        assistant_message=_message_from_plan(plan, status),
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
        "First call draft_scenario_plan. Then call get_physics_envelope or "
        "validate_scenario_request if needed. For trim, pitch, rotor-speed, "
        "yaw-in-place, or manoeuvre coaching questions, call get_trim_guidance "
        "when useful. Return an AgentPlanningDraft. "
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
    response.status = draft.status
    response.assistant_message = draft.assistant_message
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


def _status_from_plan(plan: ScenarioPlan):
    if plan.scenario_type in {"unsupported", "internal_flow", "hover_or_takeoff"}:
        return "out_of_scope"
    if plan.missing_information or plan.clarifying_questions or plan.spec is None:
        return "needs_clarification"
    return "ready_for_human_review"


def _message_from_plan(plan: ScenarioPlan, status: str) -> str:
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
    if plan.clarifying_questions:
        return plan.clarifying_questions
    return ["Revise the request into the supported external drone-aero envelope."]


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
