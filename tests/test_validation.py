from __future__ import annotations

from pathlib import Path

from whittle.models.geometry import DroneGeometrySpec
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_single_stl_geometry
from whittle.tools.validation_tools import validate_case_spec


def test_missing_geometry_file_is_flagged(tmp_path: Path) -> None:
    geometry = build_single_stl_geometry(tmp_path / "missing.stl")
    spec = build_case_spec(case_name="missing", geometry=geometry, velocity_mps=10.0)

    _, _, missing = validate_case_spec(spec)

    assert any("does not exist" in item for item in missing)


def test_missing_velocity_is_flagged(tmp_path: Path) -> None:
    geometry_file = tmp_path / "drone.stl"
    geometry_file.write_bytes(b"short")
    geometry: DroneGeometrySpec = build_single_stl_geometry(geometry_file)
    spec = build_case_spec(case_name="bad_velocity", geometry=geometry, velocity_mps=0.0)

    _, _, missing = validate_case_spec(spec)

    assert "reference_velocity_mps must be positive." in missing

