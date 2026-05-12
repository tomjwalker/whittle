"""Deterministic scenario planner for pre-agent V1 shakedown."""

from __future__ import annotations

import re

from whittle.models.planning import PhysicsEnvelope, ScenarioIntent, ScenarioPlan, ScenarioType
from whittle.models.reports import TraceEvent
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_legacy_box_geometry
from whittle.tools.performance_guidance import (
    get_motion_rotor_command,
    rotor_speed_guidance_to_patch_omega_map,
)
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE, validate_physics_envelope

_SPEED_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:m/s|metres?\s+per\s+second|meters?\s+per\s+second)",
    re.IGNORECASE,
)
_ANGLE_RE = re.compile(
    r"(?P<axis>roll|pitch|yaw)[^\d+-]*(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?:deg|degree|degrees)?",
    re.IGNORECASE,
)
_OMEGA_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?:rad/s|rad\s*s\^-?1|radians?\s+per\s+second)",
    re.IGNORECASE,
)
_YAW_RATE_RE = re.compile(
    r"(?:yaw(?:ing)?(?:\s+rate)?[^\d+-]*)?"
    r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?:deg/s|degrees?\s+per\s+second)",
    re.IGNORECASE,
)
_GENERIC_RATE_RE = re.compile(
    r"(?P<value>[+-]?\d+(?:\.\d+)?)\s*(?:deg/s|degrees?\s+per\s+second)",
    re.IGNORECASE,
)
_ZERO_SPEED_RE = re.compile(r"(?<!\d)0(?:\.0+)?\s*m/s", re.IGNORECASE)


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
    intent = _draft_intent(text, scenario_type, envelope)
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
            intent,
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
            intent,
        )

    if scenario_type == "hover_or_takeoff":
        if _is_yaw_in_place_request(text):
            missing.append(
                "Yaw-in-place needs a later manoeuvre model with differential rotor speeds."
            )
            questions.extend(
                [
                    "What yaw rate did you have in mind, in degrees per second? "
                    "A cautious small-quadcopter demo value would be around 30-90 deg/s.",
                    "Should I keep this as a future yaw-manoeuvre case, or approximate "
                    "it today as steady forward flight with MRF rotors?",
                ]
            )
        else:
            missing.append("Hover/takeoff needs a later ground-effect or rotor-source setup.")
            questions.append(
                "For today, should I approximate this as forward flight with MRF rotors?"
            )
        return _plan(
            request,
            scenario_type,
            assumptions,
            warnings,
            missing,
            questions,
            trace_events,
            intent,
        )

    if scenario_type == "trim_guidance":
        missing.append(
            "Trim guidance needs a later force-balance model or a sweep, "
            "not a single validated case."
        )
        questions.extend(
            [
                "Should I propose a small pitch/rotor-speed sweep for this speed?",
                "Do you want the first supported approximation as steady cruise with MRF rotors?",
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
            intent,
        )

    if scenario_type == "static_hover_mrf":
        velocity = 0.0
        roll, pitch, yaw = _extract_attitude(text)
        rotor_model = _extract_rotor_model(text, scenario_type)
        if rotor_model == "none":
            rotor_model = "mrf"
        rotor_omega = _extract_mrf_omega(text) or envelope.default_mrf_omega_rad_s
        flow_regime = (
            "steady_incompressible_static_rotor_disk_hover"
            if rotor_model == "rotor_disk"
            else "steady_incompressible_static_mrf_hover"
        )
        assumptions.extend(
            [
                f"Using zero freestream for a static {rotor_model} hover smoke case.",
                f"Using rotor omega of {rotor_omega:g} rad/s.",
                "No floor, ground effect, takeoff transient, or solved trim balance is modelled.",
            ]
        )
        rotor_label = "MRF" if rotor_model == "mrf" else "rotor-disk"
        warnings.append(
            f"Static {rotor_label} hover is a crude educational approximation, "
            "not a validated hover CFD setup."
        )
        spec = build_case_spec(
            case_name=case_name,
            geometry=build_legacy_box_geometry(),
            velocity_mps=velocity,
            flow_regime=flow_regime,
            rotor_model=rotor_model,
            mrf_omega_rad_s=rotor_omega,
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
                    message="Deterministic planner extracted static MRF hover fields.",
                    data={
                        "scenario_type": scenario_type,
                        "velocity_mps": velocity,
                        "roll_deg": roll,
                        "pitch_deg": pitch,
                        "yaw_deg": yaw,
                        "rotor_model": rotor_model,
                        "rotor_omega_rad_s": rotor_omega,
                    },
                ),
                TraceEvent(
                    event_type="IntentDrafted",
                    message="Scenario intent drafted before case-spec validation.",
                    data={
                        "objective": intent.objective,
                        "state": intent.state,
                        "rotor_strategy": intent.rotor_strategy,
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
            intent,
            spec=spec,
        )

    if scenario_type == "motion_proxy":
        u_mps = _motion_u_mps(text, envelope)
        v_mps, w_mps = 0.0, 0.0
        roll, pitch, yaw = _extract_attitude(text)
        roll_rate, pitch_rate, yaw_rate = _extract_motion_rates(text)
        command = get_motion_rotor_command(
            u_mps=u_mps,
            v_mps=v_mps,
            w_mps=w_mps,
            roll_deg=roll,
            pitch_deg=pitch,
            yaw_deg=yaw,
            roll_rate_deg_s=roll_rate,
            pitch_rate_deg_s=pitch_rate,
            yaw_rate_deg_s=yaw_rate,
        )
        assumptions.extend(
            [
                "Motion request is represented as a steady differential-MRF proxy.",
                f"Using translational freestream u={u_mps:g} m/s, v=0 m/s, w=0 m/s.",
                "Rotor speeds come from the transparent heuristic motion-command table.",
            ]
        )
        warnings.extend(command.limitations[:4])
        spec = build_case_spec(
            case_name=case_name,
            geometry=build_legacy_box_geometry(),
            velocity_mps=u_mps,
            flow_regime="steady_incompressible_motion_proxy_mrf",
            rotor_model="mrf",
            mrf_omega_by_patch_rad_s=rotor_speed_guidance_to_patch_omega_map(
                command.rotor_speeds_rad_s
            ),
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
                    message="Deterministic planner extracted motion-proxy fields.",
                    data={
                        "scenario_type": scenario_type,
                        "u_mps": u_mps,
                        "v_mps": v_mps,
                        "w_mps": w_mps,
                        "roll_deg": roll,
                        "pitch_deg": pitch,
                        "yaw_deg": yaw,
                        "roll_rate_deg_s": roll_rate,
                        "pitch_rate_deg_s": pitch_rate,
                        "yaw_rate_deg_s": yaw_rate,
                        "rotor_model": "mrf",
                    },
                ),
                TraceEvent(
                    event_type="MotionRotorCommandRun",
                    message="Heuristic motion-to-rotor command was generated.",
                    data=command.model_dump(mode="json"),
                ),
                TraceEvent(
                    event_type="IntentDrafted",
                    message="Scenario intent drafted before case-spec validation.",
                    data={
                        "objective": intent.objective,
                        "state": intent.state,
                        "rotor_strategy": intent.rotor_strategy,
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
            intent,
            spec=spec,
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
            intent,
        )

    velocity = _extract_speed(text)
    if velocity is None:
        velocity = envelope.default_cruise_velocity_mps
        assumptions.append(f"Using default cruise velocity of {velocity:g} m/s.")

    roll, pitch, yaw = _extract_attitude(text)
    rotor_model = _extract_rotor_model(text, scenario_type)
    rotor_omega = envelope.default_mrf_omega_rad_s
    if rotor_model in {"mrf", "rotor_disk"}:
        extracted_omega = _extract_mrf_omega(text)
        if extracted_omega is not None:
            rotor_omega = extracted_omega
            assumptions.append(f"Using requested rotor omega of {rotor_omega:g} rad/s.")
        else:
            assumptions.append(f"Using default rotor omega of {rotor_omega:g} rad/s.")

    spec = build_case_spec(
        case_name=case_name,
        geometry=build_legacy_box_geometry(),
        velocity_mps=velocity,
        rotor_model=rotor_model,
        mrf_omega_rad_s=rotor_omega,
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
                event_type="IntentDrafted",
                message="Scenario intent drafted before case-spec validation.",
                data={
                    "objective": intent.objective,
                    "state": intent.state,
                    "rotor_strategy": intent.rotor_strategy,
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
        intent,
        spec=spec,
    )


def _classify_request(text: str) -> ScenarioType:
    if any(term in text for term in ("weapon", "target", "evasion", "payload attack")):
        return "unsupported"
    if any(term in text for term in ("duct", "internal flow", "pipe")):
        return "internal_flow"
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
        return "vague_request"
    if _is_trim_guidance_request(text):
        return "trim_guidance"
    if _is_static_hover_request(text):
        return "static_hover_mrf"
    if _is_motion_proxy_request(text):
        return "motion_proxy"
    if any(
        term in text
        for term in (
            "hover",
            "takeoff",
            "take-off",
            "landing",
            "spin in place",
            "spinning in place",
            "rotate in place",
            "yaw in place",
            "yawing in place",
        )
    ):
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
        suffix = text[match.end() : match.end() + 12]
        if suffix.startswith("/s") or "per second" in suffix:
            continue
        values[match.group("axis").lower()] = float(match.group("value"))
    return values["roll"], values["pitch"], values["yaw"]


def _extract_rotor_model(text: str, scenario_type: ScenarioType = "external_cruise") -> str:
    if any(
        term in text
        for term in (
            "ignore prop",
            "ignore rotor",
            "no prop",
            "no rotor",
            "without prop",
            "without rotor",
            "no rotation",
            "no mrf",
        )
    ):
        return "none"
    if any(term in text for term in ("prop", "rotor", "downwash", "swirl", "mrf", "spinning")):
        if any(
            term in text
            for term in (
                "rotor disk",
                "rotordisk",
                "actuator",
                "source term",
                "stronger downwash",
                "downwash",
            )
        ):
            return "rotor_disk"
        return "mrf"
    if scenario_type in {"external_cruise", "attitude_transform"}:
        return "mrf"
    return "none"


def _extract_mrf_omega(text: str) -> float | None:
    match = _OMEGA_RE.search(text)
    if not match:
        return None
    return float(match.group("value"))


def _extract_yaw_rate(text: str) -> float | None:
    if "yaw" not in text and "spin" not in text and "rotate" not in text:
        return None
    match = _YAW_RATE_RE.search(text)
    if not match:
        return None
    return float(match.group("value"))


def _extract_motion_rates(text: str) -> tuple[float, float, float]:
    return (
        _extract_axis_rate(text, "roll"),
        _extract_axis_rate(text, "pitch"),
        _extract_axis_rate(text, "yaw"),
    )


def _extract_axis_rate(text: str, axis: str) -> float:
    axis_terms = _axis_terms(axis)
    if not any(term in text for term in axis_terms):
        return 0.0

    match = re.search(
        rf"(?:{axis}|{axis}ing)(?:\s+rate)?[^\d+-]*"
        rf"(?P<value>[+-]?\d+(?:\.\d+)?)\s*"
        rf"(?:deg/s|degrees?\s+per\s+second)",
        text,
        re.IGNORECASE,
    )
    if match:
        return float(match.group("value"))

    generic_match = _GENERIC_RATE_RE.search(text)
    mentioned_axes = [
        candidate for candidate in ("roll", "pitch", "yaw") if _axis_is_mentioned(text, candidate)
    ]
    if generic_match and len(mentioned_axes) == 1 and mentioned_axes[0] == axis:
        return float(generic_match.group("value"))

    if "slow" in text or "gently" in text:
        return 30.0
    if "medium" in text or "moderate" in text:
        return 60.0
    if "fast" in text or "aggressive" in text:
        return 90.0
    return 45.0


def _axis_terms(axis: str) -> tuple[str, ...]:
    if axis == "yaw":
        return ("yaw", "yawing", "spin", "spinning", "rotate", "rotating")
    if axis == "roll":
        return ("roll", "rolling")
    return ("pitch", "pitching")


def _axis_is_mentioned(text: str, axis: str) -> bool:
    return any(term in text for term in _axis_terms(axis))


def _motion_u_mps(text: str, envelope: PhysicsEnvelope) -> float:
    speed = _extract_speed(text)
    if speed is not None:
        return speed
    if any(term in text for term in ("in place", "hover", "zero freestream", "0 freestream")):
        return 0.0
    return envelope.default_cruise_velocity_mps


def _draft_intent(
    text: str,
    scenario_type: ScenarioType,
    envelope: PhysicsEnvelope,
) -> ScenarioIntent:
    velocity = _extract_speed(text)
    roll, pitch, yaw = _extract_attitude(text)
    omega = _extract_mrf_omega(text)
    roll_rate, pitch_rate, yaw_rate = _extract_motion_rates(text)
    environment = "floor_or_ground" if _requires_floor_or_ground(text) else "unbounded_external"

    common_fields: dict[str, str | float | bool] = {}
    if velocity is not None:
        common_fields["velocity_mps"] = velocity
    if omega is not None:
        common_fields["mrf_omega_rad_s"] = omega
    if abs(yaw_rate) > 0:
        common_fields["yaw_rate_deg_s"] = yaw_rate
    if abs(roll_rate) > 0:
        common_fields["roll_rate_deg_s"] = roll_rate
    if abs(pitch_rate) > 0:
        common_fields["pitch_rate_deg_s"] = pitch_rate
    if any(value != 0 for value in (roll, pitch, yaw)):
        common_fields["roll_deg"] = roll
        common_fields["pitch_deg"] = pitch
        common_fields["yaw_deg"] = yaw

    if scenario_type == "static_hover_mrf":
        return ScenarioIntent(
            objective="static_hover",
            state="ready_for_spec",
            rotor_strategy="mrf_smoke",
            environment="unbounded_external",
            confidence=0.86,
            requested_velocity_mps=0.0,
            requested_roll_deg=roll,
            requested_pitch_deg=pitch,
            requested_yaw_deg=yaw,
            requested_mrf_omega_rad_s=omega or envelope.default_mrf_omega_rad_s,
            inferred_fields=common_fields | {"velocity_mps": 0.0},
            assumptions=[
                "Zero freestream is being treated as a static MRF smoke case.",
                "Rotor speed is a smoke-setting input, not a solved hover trim result.",
            ],
            warnings=[
                "This intent is not a takeoff, ground-effect, or validated hover-trim model."
            ],
            recommended_next_step="Review the static hover assumptions before writing a case.",
        )

    if scenario_type == "motion_proxy":
        u_mps = _motion_u_mps(text, envelope)
        command = get_motion_rotor_command(
            u_mps=u_mps,
            v_mps=0.0,
            w_mps=0.0,
            roll_deg=roll,
            pitch_deg=pitch,
            yaw_deg=yaw,
            roll_rate_deg_s=roll_rate,
            pitch_rate_deg_s=pitch_rate,
            yaw_rate_deg_s=yaw_rate,
        )
        return ScenarioIntent(
            objective="motion_proxy",
            state="ready_for_spec",
            rotor_strategy="differential_mrf_proxy",
            environment="unbounded_external",
            confidence=0.74,
            requested_velocity_mps=u_mps,
            requested_u_mps=u_mps,
            requested_v_mps=0.0,
            requested_w_mps=0.0,
            requested_roll_rate_deg_s=roll_rate,
            requested_pitch_rate_deg_s=pitch_rate,
            requested_yaw_rate_deg_s=yaw_rate,
            requested_roll_deg=roll,
            requested_pitch_deg=pitch,
            requested_yaw_deg=yaw,
            requested_mrf_omega_rad_s=command.base_omega_rad_s,
            inferred_fields=common_fields
            | {
                "u_mps": u_mps,
                "v_mps": 0.0,
                "w_mps": 0.0,
                "base_omega_rad_s": command.base_omega_rad_s,
            },
            assumptions=[
                "The manoeuvre is approximated as a steady differential-MRF proxy.",
                (
                    "Rate requests become per-rotor omega differentials; body "
                    "angular velocity is not imposed."
                ),
            ],
            warnings=command.limitations[:3],
            recommended_next_step="Review the motion proxy before writing the case.",
        )

    if scenario_type == "hover_or_takeoff" and _is_yaw_in_place_request(text):
        return ScenarioIntent(
            objective="yaw_manoeuvre",
            state="blocked",
            rotor_strategy="differential_rotor_model_required",
            environment=environment,
            confidence=0.82,
            requested_yaw_rate_deg_s=yaw_rate,
            inferred_fields=common_fields,
            missing_information=[
                "Yaw-rate-to-rotor-speed mapping needs a performance model or lookup table.",
                "The current steady OpenFOAM writer cannot impose yaw_dot directly.",
            ],
            assumptions=[
                "A yaw manoeuvre would use differential rotor torque between opposite pairs."
            ],
            recommended_next_step=(
                "Ask for yaw rate, then keep this as a future differential-rotor workflow."
            ),
        )

    if scenario_type == "hover_or_takeoff":
        return ScenarioIntent(
            objective="takeoff_or_ground_effect",
            state="blocked",
            rotor_strategy="performance_table_required",
            environment=environment,
            confidence=0.78,
            inferred_fields=common_fields,
            missing_information=[
                "Floor, takeoff, landing, and ground-effect cases need a later physics setup."
            ],
            recommended_next_step="Reframe as static hover MRF smoke or forward-flight MRF.",
        )

    if scenario_type == "trim_guidance":
        return ScenarioIntent(
            objective="trim_or_performance_sweep",
            state="needs_clarification",
            rotor_strategy="performance_table_required",
            environment="unbounded_external",
            confidence=0.8,
            requested_velocity_mps=velocity,
            requested_roll_deg=roll,
            requested_pitch_deg=pitch,
            requested_yaw_deg=yaw,
            requested_mrf_omega_rad_s=omega,
            inferred_fields=common_fields,
            missing_information=[
                "Pitch and rotor speeds need a sweep, table, or trim solver "
                "before claiming balance."
            ],
            recommended_next_step="Propose a pitch/omega sweep and evaluate forces and moments.",
        )

    if scenario_type == "vague_request":
        return ScenarioIntent(
            objective="design_exploration",
            state="needs_clarification",
            rotor_strategy="unknown",
            environment="unknown",
            confidence=0.58,
            inferred_fields=common_fields,
            missing_information=[
                "Need scenario type, reference speed, and rotor modelling choice."
            ],
            recommended_next_step="Ask the user to choose cruise, attitude, hover smoke, or sweep.",
        )

    if scenario_type == "internal_flow":
        return ScenarioIntent(
            objective="internal_flow",
            state="blocked",
            rotor_strategy="none",
            environment="internal",
            confidence=0.75,
            inferred_fields=common_fields,
            missing_information=["The current writer only supports external drone flow."],
            recommended_next_step="Ask whether to reframe as external flow.",
        )

    if scenario_type == "unsupported":
        return ScenarioIntent(
            objective="unsupported",
            state="blocked",
            rotor_strategy="unknown",
            environment="unknown",
            confidence=0.8,
            inferred_fields=common_fields,
            missing_information=["Request is outside the civil educational CFD scope."],
            recommended_next_step="Ask for a civil drone aerodynamics request.",
        )

    if scenario_type == "attitude_transform":
        objective = "attitude_hold"
    else:
        objective = "external_cruise"
    rotor_model = _extract_rotor_model(text, scenario_type)
    if rotor_model == "mrf":
        rotor_strategy = "mrf_smoke"
    elif rotor_model == "rotor_disk":
        rotor_strategy = "rotor_disk_source"
    else:
        rotor_strategy = "none"
    return ScenarioIntent(
        objective=objective,
        state="ready_for_spec",
        rotor_strategy=rotor_strategy,
        environment="unbounded_external",
        confidence=0.82,
        requested_velocity_mps=velocity or envelope.default_cruise_velocity_mps,
        requested_roll_deg=roll,
        requested_pitch_deg=pitch,
        requested_yaw_deg=yaw,
        requested_mrf_omega_rad_s=omega,
        inferred_fields=common_fields,
        assumptions=["Missing speed falls back to the default cruise velocity."],
        recommended_next_step="Draft and validate a SimulationCaseSpec.",
    )


def _is_yaw_in_place_request(text: str) -> bool:
    return any(
        term in text
        for term in (
            "yawing in place",
            "yaw in place",
            "spinning in place",
            "spin in place",
            "rotate in place",
        )
    )


def _is_motion_proxy_request(text: str) -> bool:
    if _requires_floor_or_ground(text):
        return False
    if any(term in text for term in ("takeoff", "take-off", "landing")):
        return False
    if _is_yaw_in_place_request(text):
        return True
    if "deg/s" in text or "degrees per second" in text:
        return any(_axis_is_mentioned(text, axis) for axis in ("roll", "pitch", "yaw"))
    return any(
        term in text
        for term in (
            "rolling in place",
            "roll in place",
            "pitching in place",
            "pitch in place",
            "slowly yaw",
            "slow yaw",
            "slowly roll",
            "slow roll",
            "slowly pitch",
            "slow pitch",
            "combined manoeuvre",
            "combined maneuver",
        )
    )


def _is_static_hover_request(text: str) -> bool:
    if _requires_floor_or_ground(text):
        return False
    if any(term in text for term in ("takeoff", "take-off", "landing")):
        return False
    hover_terms = (
        "hover",
        "hover-in-place",
        "hover in place",
        "zero freestream",
        "0 freestream",
        "0 onset",
    )
    if not any(term in text for term in hover_terms) and not _ZERO_SPEED_RE.search(text):
        return False
    if any(term in text for term in ("yawing in place", "yaw in place", "spin", "rotate")):
        return False
    return True


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


def _is_trim_guidance_request(text: str) -> bool:
    has_trim_language = any(
        term in text
        for term in (
            "what kind of pitch",
            "what pitch",
            "which pitch",
            "rotor speeds",
            "rotor speed",
            "support that drone speed",
            "support this drone speed",
            "trim",
        )
    )
    has_speed = _extract_speed(text) is not None or "faster" in text or "speed" in text
    return has_trim_language and has_speed


def _plan(
    request: str,
    scenario_type: ScenarioType,
    assumptions: list[str],
    warnings: list[str],
    missing: list[str],
    questions: list[str],
    trace_events: list[TraceEvent],
    intent: ScenarioIntent,
    *,
    spec=None,
) -> ScenarioPlan:
    if not any(event.event_type == "IntentDrafted" for event in trace_events):
        trace_events.append(
            TraceEvent(
                event_type="IntentDrafted",
                message="Scenario intent drafted before case-spec validation.",
                data={
                    "objective": intent.objective,
                    "state": intent.state,
                    "rotor_strategy": intent.rotor_strategy,
                },
            )
        )
    return ScenarioPlan(
        user_request=request,
        scenario_type=scenario_type,
        intent=intent,
        spec=spec,
        assumptions=assumptions,
        warnings=warnings,
        missing_information=missing,
        clarifying_questions=questions,
        trace_events=trace_events,
    )
