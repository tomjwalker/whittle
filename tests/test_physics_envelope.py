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
