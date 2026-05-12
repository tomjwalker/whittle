from __future__ import annotations

from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_legacy_box_geometry
from whittle.tools.validation_tools import validate_case_spec


def test_high_but_subhard_velocity_is_warned() -> None:
    spec = build_case_spec(
        case_name="fast",
        geometry=build_legacy_box_geometry(),
        velocity_mps=30.0,
    )

    _, warnings, missing = validate_case_spec(spec)

    assert not missing
    assert any("above the typical small-quadcopter cruise range" in item for item in warnings)


def test_zero_velocity_static_mrf_hover_is_allowed_with_warning() -> None:
    spec = build_case_spec(
        case_name="static_hover",
        geometry=build_legacy_box_geometry(),
        velocity_mps=0.0,
        flow_regime="steady_incompressible_static_mrf_hover",
        rotor_model="mrf",
    )

    checks, warnings, missing = validate_case_spec(spec)

    assert not missing
    assert any("static/differential MRF proxy" in item for item in checks)
    assert any("Zero-freestream MRF proxy" in item for item in warnings)


def test_zero_velocity_non_hover_case_is_blocked() -> None:
    spec = build_case_spec(
        case_name="zero_cruise",
        geometry=build_legacy_box_geometry(),
        velocity_mps=0.0,
    )

    _, _, missing = validate_case_spec(spec)

    assert any("must be positive" in item for item in missing)


def test_hard_velocity_limit_blocks_case() -> None:
    spec = build_case_spec(
        case_name="too_fast",
        geometry=build_legacy_box_geometry(),
        velocity_mps=120.0,
    )

    _, _, missing = validate_case_spec(spec)

    assert any("hard limit" in item for item in missing)


def test_attitude_limit_blocks_case() -> None:
    spec = build_case_spec(
        case_name="too_much_pitch",
        geometry=build_legacy_box_geometry(),
        velocity_mps=5.0,
        pitch_deg=45.0,
    )

    _, _, missing = validate_case_spec(spec)

    assert any("pitch_angle_deg exceeds" in item for item in missing)
