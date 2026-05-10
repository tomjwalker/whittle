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
