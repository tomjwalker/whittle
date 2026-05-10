from __future__ import annotations

import struct
from pathlib import Path

from whittle.models.geometry import DroneGeometrySpec, GeometrySurfaceSpec
from whittle.tools.attitude_suite import ATTITUDE_SMOKE_CASES, write_attitude_smoke_suite


def test_attitude_suite_writes_b_and_c_cases(tmp_path: Path) -> None:
    reports = write_attitude_smoke_suite(tmp_path, geometry=_tiny_legacy_geometry(tmp_path))

    assert [report.case_name for report in reports] == [
        case.directory_name for case in ATTITUDE_SMOKE_CASES
    ]
    for report in reports:
        case_dir = tmp_path / report.case_name
        assert report.can_run
        assert (case_dir / "constant/MRFProperties").exists()
        assert (case_dir / "system/topoSetDict").exists()
        assert (case_dir / "case_report.json").exists()


def test_combined_case_has_nonzero_roll_pitch_and_yaw(tmp_path: Path) -> None:
    reports = write_attitude_smoke_suite(tmp_path, geometry=_tiny_legacy_geometry(tmp_path))
    combined = next(report for report in reports if report.case_name.endswith("combined_smoke"))

    assert combined.spec.roll_angle_deg != 0.0
    assert combined.spec.pitch_angle_deg != 0.0
    assert combined.spec.yaw_angle_deg != 0.0


def _tiny_legacy_geometry(tmp_path: Path) -> DroneGeometrySpec:
    surfaces = []
    for file_name, patch_name, role in (
        ("body.stl", "drone_body", "body"),
        ("prop_fr.stl", "propeller_fr", "propeller"),
        ("prop_br.stl", "propeller_br", "propeller"),
        ("prop_fl.stl", "propeller_fl", "propeller"),
        ("prop_bl.stl", "propeller_bl", "propeller"),
    ):
        path = tmp_path / file_name
        _write_binary_stl(path)
        surfaces.append(
            GeometrySurfaceSpec(
                source_path=path,
                target_file_name=file_name,
                patch_name=patch_name,
                role=role,
            )
        )
    return DroneGeometrySpec(
        name="legacy_box_quadcopter",
        geometry_mode="surface_set",
        surfaces=surfaces,
        units="m",
    )


def _write_binary_stl(path: Path) -> None:
    header = b"test binary stl".ljust(80, b" ")
    triangle_count = struct.pack("<I", 1)
    triangle = struct.pack(
        "<12fH",
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0,
    )
    path.write_bytes(header + triangle_count + triangle)
