from __future__ import annotations

from whittle.tools.performance_guidance import (
    get_cruise_performance_guidance,
    get_motion_rotor_command,
)


def test_performance_guidance_returns_signed_baseline_rotor_speeds() -> None:
    guidance = get_cruise_performance_guidance(5.0)

    assert guidance.recommended_pitch_deg == 0.0
    assert guidance.baseline_omega_rad_s == 1000.0
    assert guidance.baseline_rotor_speeds_rad_s.propeller_fl_rad_s == -1000.0
    assert guidance.baseline_rotor_speeds_rad_s.propeller_fr_rad_s == 1000.0
    assert guidance.baseline_rotor_speeds_rad_s.propeller_bl_rad_s == 1000.0
    assert guidance.baseline_rotor_speeds_rad_s.propeller_br_rad_s == -1000.0


def test_performance_guidance_interpolates_between_table_points() -> None:
    guidance = get_cruise_performance_guidance(12.5)

    assert guidance.recommended_pitch_deg == 8.0
    assert guidance.baseline_omega_rad_s == 1250.0


def test_performance_guidance_provides_yaw_proxy_without_claiming_writeable_yaw_dot() -> None:
    guidance = get_cruise_performance_guidance(5.0, yaw_rate_deg_s=45.0)

    assert guidance.mode == "yaw_manoeuvre_proxy"
    assert guidance.yaw_proxy_rotor_speeds_rad_s is not None
    assert guidance.yaw_proxy_rotor_speeds_rad_s.propeller_fr_rad_s > 1000.0
    assert guidance.yaw_proxy_rotor_speeds_rad_s.propeller_bl_rad_s > 1000.0
    assert any("cannot impose yaw_dot" in item for item in guidance.limitations)


def test_motion_rotor_command_combines_attitude_rate_deltas() -> None:
    command = get_motion_rotor_command(
        u_mps=5.0,
        roll_rate_deg_s=30.0,
        yaw_rate_deg_s=45.0,
    )

    assert command.base_omega_rad_s == 1000.0
    assert command.is_rolling is True
    assert command.is_pitching is False
    assert command.is_yawing is True
    assert command.rotor_speeds_rad_s.propeller_fr_rad_s > 1000.0
    assert command.rotor_speeds_rad_s.propeller_bl_rad_s > 1000.0
    assert command.rotor_speeds_rad_s.propeller_fl_rad_s > -1000.0
    assert command.rotor_speeds_rad_s.propeller_br_rad_s < -900.0
    assert any("not imposed as body angular velocities" in item for item in command.limitations)
