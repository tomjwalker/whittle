from __future__ import annotations

from whittle.tools.scenario_planner import plan_case_request


def test_planner_extracts_cruise_speed_and_mrf_rotors() -> None:
    plan = plan_case_request(
        "Set up external cruise over a quadcopter at 10 m/s with spinning propellers.",
        case_name="cruise",
    )

    assert not plan.missing_information
    assert plan.spec is not None
    assert plan.scenario_type == "external_cruise"
    assert plan.intent is not None
    assert plan.intent.objective == "external_cruise"
    assert plan.intent.state == "ready_for_spec"
    assert plan.spec.reference_velocity_mps == 10.0
    assert plan.spec.rotor_model == "mrf"
    assert len(plan.spec.mrf_zones) == 4


def test_planner_extracts_attitude_angles() -> None:
    plan = plan_case_request(
        "Run a pitched drone case at 5 m/s with pitch 10 degrees, roll 2 deg, yaw -3 deg.",
        case_name="attitude",
    )

    assert plan.spec is not None
    assert plan.scenario_type == "attitude_transform"
    assert plan.spec.pitch_angle_deg == 10.0
    assert plan.spec.roll_angle_deg == 2.0
    assert plan.spec.yaw_angle_deg == -3.0


def test_planner_accepts_static_hover_without_floor_as_mrf_smoke_case() -> None:
    plan = plan_case_request(
        "I'd like to simulate hover-in-place, no need for the floor, rotors at 1200 rad/s.",
        case_name="hover_static",
    )

    assert plan.scenario_type == "static_hover_mrf"
    assert plan.intent is not None
    assert plan.intent.objective == "static_hover"
    assert plan.intent.state == "ready_for_spec"
    assert plan.intent.rotor_strategy == "mrf_smoke"
    assert not plan.missing_information
    assert plan.spec is not None
    assert plan.spec.flow_regime == "steady_incompressible_static_mrf_hover"
    assert plan.spec.reference_velocity_mps == 0.0
    assert plan.spec.rotor_model == "mrf"
    assert max(abs(zone.omega_rad_s) for zone in plan.spec.mrf_zones) == 1200.0
    assert any("approximation" in item for item in plan.warnings)


def test_planner_keeps_floor_takeoff_out_of_current_writer() -> None:
    plan = plan_case_request("I want to simulate hover takeoff from a floor.")

    assert plan.scenario_type == "hover_or_takeoff"
    assert plan.intent is not None
    assert plan.intent.objective == "takeoff_or_ground_effect"
    assert plan.intent.state == "blocked"
    assert plan.spec is None
    assert any("ground-effect" in item for item in plan.missing_information)


def test_planner_writes_yaw_manoeuvre_as_motion_proxy() -> None:
    plan = plan_case_request("I want to simulate yawing in place at 45 deg/s.")

    assert plan.scenario_type == "motion_proxy"
    assert plan.intent is not None
    assert plan.intent.objective == "motion_proxy"
    assert plan.intent.state == "ready_for_spec"
    assert plan.intent.rotor_strategy == "differential_mrf_proxy"
    assert plan.intent.requested_yaw_rate_deg_s == 45.0
    assert plan.spec is not None
    assert plan.spec.flow_regime == "steady_incompressible_motion_proxy_mrf"
    assert plan.spec.reference_velocity_mps == 0.0
    assert plan.spec.rotor_model == "mrf"
    by_patch = {zone.source_patch: zone.omega_rad_s for zone in plan.spec.mrf_zones}
    assert by_patch["propeller_fr"] > 1000.0
    assert by_patch["propeller_bl"] > 1000.0
    assert any(event.event_type == "MotionRotorCommandRun" for event in plan.trace_events)
    assert any("not imposed" in item for item in plan.warnings)


def test_planner_flags_vague_request() -> None:
    plan = plan_case_request("make this more aerodynamic")

    assert plan.scenario_type == "vague_request"
    assert plan.spec is None
    assert plan.missing_information
    assert plan.clarifying_questions


def test_planner_keeps_internal_flow_out_of_external_writer() -> None:
    plan = plan_case_request("simulate internal duct flow at 10 m/s")

    assert plan.scenario_type == "internal_flow"
    assert plan.spec is None
    assert any("Internal duct flow" in item for item in plan.missing_information)
