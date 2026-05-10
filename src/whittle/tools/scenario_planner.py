"""Deterministic scenario planner for pre-agent V1 shakedown."""

from __future__ import annotations

import re

from whittle.models.planning import PhysicsEnvelope, ScenarioPlan, ScenarioType
from whittle.models.reports import TraceEvent
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_legacy_box_geometry
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE, validate_physics_envelope

_SPEED_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:m/s|metres?\s+per\s+second|meters?\s+per\s+second)",
    re.IGNORECASE,
)
_ANGLE_RE = re.compile(
    r"(?P<axis>roll|pitch|yaw)[^\d+-]*(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)?",
    re.IGNORECASE,
)


def plan_case_request(
    user_request: str,
    *,
    case_name: str = "planned_case",
    envelope: PhysicsEnvelope = DEFAULT_PHYSICS_ENVELOPE,
) -> ScenarioPlan:
    """Map a rough request into typed case state when enough information is present."""

    request = user_request.strip()
    text = request.lower()
    trace_events = [
        TraceEvent(
            event_type="RequestReceived",
            message="Natural-language scenario request received.",
            data={"request": request},
        )
    ]

    scenario_type = _classify_request(text)
    assumptions: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []
    questions: list[str] = []

    if scenario_type == "unsupported":
        missing.append("Request is outside the civil educational CFD setup envelope.")
        questions.append("Can you restate this as a civil drone aerodynamics setup request?")
        return _plan(
            request,
            scenario_type,
            assumptions,
            warnings,
            missing,
            questions,
            trace_events,
        )

    if scenario_type == "internal_flow":
        missing.append("Internal duct flow is outside the current external-drone-aero writer.")
        questions.append("Should this be reframed as external flow over the drone geometry?")
        return _plan(
            request,
            scenario_type,
            assumptions,
            warnings,
            missing,
            questions,
            trace_events,
        )

    if scenario_type == "hover_or_takeoff":
        missing.append("Hover/takeoff needs a later ground-effect or rotor-source setup.")
        questions.append("For today, should I approximate this as forward flight with MRF rotors?")
        return _plan(
            request,
            scenario_type,
            assumptions,
            warnings,
            missing,
            questions,
            trace_events,
        )

    if scenario_type == "vague_request":
        missing.append("Request does not specify a CFD scenario, velocity, or geometry.")
        questions.extend(
            [
                "Do you want external cruise, a pitched attitude case, or a rotor/downwash case?",
                "What freestream speed should be used in m/s?",
            ]
        )
        return _plan(
            request,
            scenario_type,
            assumptions,
            warnings,
            missing,
            questions,
            trace_events,
        )

    velocity = _extract_speed(text)
    if velocity is None:
        velocity = envelope.default_cruise_velocity_mps
        assumptions.append(f"Using default cruise velocity of {velocity:g} m/s.")

    roll, pitch, yaw = _extract_attitude(text)
    rotor_model = _extract_rotor_model(text)
    mrf_omega = envelope.default_mrf_omega_rad_s
    if rotor_model == "mrf":
        assumptions.append(f"Using default MRF omega of {mrf_omega:g} rad/s.")
    elif "prop" not in text and "rotor" not in text:
        questions.append("Should propellers be ignored, or should MRF rotors be included?")

    spec = build_case_spec(
        case_name=case_name,
        geometry=build_legacy_box_geometry(),
        velocity_mps=velocity,
        rotor_model=rotor_model,
        mrf_omega_rad_s=mrf_omega,
        roll_deg=roll,
        pitch_deg=pitch,
        yaw_deg=yaw,
    )
    checks, envelope_warnings, envelope_missing = validate_physics_envelope(spec, envelope)
    warnings.extend(envelope_warnings)
    missing.extend(envelope_missing)

    trace_events.extend(
        [
            TraceEvent(
                event_type="FieldsExtracted",
                message="Deterministic planner extracted initial fields.",
                data={
                    "scenario_type": scenario_type,
                    "velocity_mps": velocity,
                    "roll_deg": roll,
                    "pitch_deg": pitch,
                    "yaw_deg": yaw,
                    "rotor_model": rotor_model,
                },
            ),
            TraceEvent(
                event_type="ValidationRun",
                message="Physics-envelope checks completed.",
                data={"check_count": len(checks), "missing_count": len(missing)},
            ),
        ]
    )

    return _plan(
        request,
        scenario_type,
        assumptions,
        warnings,
        missing,
        questions,
        trace_events,
        spec=spec,
    )


def _classify_request(text: str) -> ScenarioType:
    if any(term in text for term in ("weapon", "target", "evasion", "payload attack")):
        return "unsupported"
    if any(term in text for term in ("duct", "internal flow", "pipe")):
        return "internal_flow"
    if any(term in text for term in ("hover", "takeoff", "take-off", "landing")):
        return "hover_or_takeoff"
    if any(term in text for term in ("make it aero", "more aerodynamic", "better aerodynamic")):
        return "vague_request"
    if any(term in text for term in ("roll", "pitch", "yaw")):
        return "attitude_transform"
    return "external_cruise"


def _extract_speed(text: str) -> float | None:
    match = _SPEED_RE.search(text)
    if not match:
        return None
    return float(match.group("value"))


def _extract_attitude(text: str) -> tuple[float, float, float]:
    values = {"roll": 0.0, "pitch": 0.0, "yaw": 0.0}
    for match in _ANGLE_RE.finditer(text):
        values[match.group("axis").lower()] = float(match.group("value"))
    return values["roll"], values["pitch"], values["yaw"]


def _extract_rotor_model(text: str) -> str:
    if any(term in text for term in ("ignore prop", "ignore rotor", "no rotation", "no mrf")):
        return "none"
    if any(term in text for term in ("prop", "rotor", "downwash", "swirl", "mrf", "spinning")):
        return "mrf"
    return "none"


def _plan(
    request: str,
    scenario_type: ScenarioType,
    assumptions: list[str],
    warnings: list[str],
    missing: list[str],
    questions: list[str],
    trace_events: list[TraceEvent],
    *,
    spec=None,
) -> ScenarioPlan:
    return ScenarioPlan(
        user_request=request,
        scenario_type=scenario_type,
        spec=spec,
        assumptions=assumptions,
        warnings=warnings,
        missing_information=missing,
        clarifying_questions=questions,
        trace_events=trace_events,
    )
