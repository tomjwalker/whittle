from __future__ import annotations

import math

import pytest

from whittle.tools.rotor_presets import LEGACY_BOX_MRF_RADIUS_M, build_legacy_box_mrf_zones
from whittle.tools.transform_tools import rotation_matrix, transform_point


def test_yaw_rotates_xy_positions() -> None:
    matrix = rotation_matrix(yaw_deg=90.0)

    assert transform_point((1.0, 0.0, 0.0), matrix) == pytest.approx((0.0, 1.0, 0.0))


def test_pitch_changes_front_rear_heights() -> None:
    matrix = rotation_matrix(pitch_deg=10.0)

    front = transform_point((1.0, 0.0, 0.0), matrix)
    rear = transform_point((-1.0, 0.0, 0.0), matrix)

    assert front[2] > 0.0
    assert rear[2] < 0.0


def test_roll_changes_left_right_heights() -> None:
    matrix = rotation_matrix(roll_deg=10.0)

    right = transform_point((0.0, 1.0, 0.0), matrix)
    left = transform_point((0.0, -1.0, 0.0), matrix)

    assert right[2] > 0.0
    assert left[2] < 0.0


def test_legacy_mrf_zones_are_transformed_and_keep_radius() -> None:
    zones = build_legacy_box_mrf_zones(omega_rad_s=1000.0, roll_deg=10.0, pitch_deg=5.0)

    assert len(zones) == 4
    assert [zone.cell_zone for zone in zones] == [
        "propFRZone",
        "propBRZone",
        "propFLZone",
        "propBLZone",
    ]
    assert [zone.omega_rad_s for zone in zones] == [1000.0, -1000.0, -1000.0, 1000.0]
    assert all(zone.radius_m == LEGACY_BOX_MRF_RADIUS_M for zone in zones)
    assert all(math.isclose(_norm(zone.axis), 1.0, rel_tol=1e-9) for zone in zones)


def _norm(vector: tuple[float, float, float]) -> float:
    return math.sqrt(sum(value * value for value in vector))
