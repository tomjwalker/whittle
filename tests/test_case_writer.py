from __future__ import annotations

import struct
from pathlib import Path

from whittle.openfoam.case_writer import write_openfoam_case
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_single_stl_geometry


def test_case_writer_creates_required_openfoam_files(tmp_path: Path) -> None:
    geometry_file = tmp_path / "drone.stl"
    _write_binary_stl(geometry_file)
    output_dir = tmp_path / "case"

    spec = build_case_spec(
        case_name="case",
        geometry=build_single_stl_geometry(geometry_file),
        velocity_mps=10.0,
    )
    report = write_openfoam_case(spec, output_dir)

    required_files = [
        "0/U",
        "0/p",
        "0/k",
        "0/omega",
        "0/nut",
        "constant/transportProperties",
        "constant/turbulenceProperties",
        "constant/triSurface/drone.stl",
        "system/controlDict",
        "system/blockMeshDict",
        "system/snappyHexMeshDict",
        "system/fvSchemes",
        "system/fvSolution",
        "Allrun",
        "Allclean",
        "case.foam",
        "case_report.json",
    ]
    for relative_path in required_files:
        assert (output_dir / relative_path).exists(), relative_path

    assert report.can_run
    assert "constant/triSurface/drone.stl" in report.files_written


def test_snappy_and_boundary_fields_reference_generated_patch_names(tmp_path: Path) -> None:
    geometry_file = tmp_path / "drone.stl"
    _write_binary_stl(geometry_file)
    output_dir = tmp_path / "case"

    spec = build_case_spec(
        case_name="case",
        geometry=build_single_stl_geometry(geometry_file),
        velocity_mps=10.0,
    )
    write_openfoam_case(spec, output_dir)

    snappy = (output_dir / "system/snappyHexMeshDict").read_text(encoding="utf-8")
    velocity = (output_dir / "0/U").read_text(encoding="utf-8")
    pressure = (output_dir / "0/p").read_text(encoding="utf-8")

    assert "drone.stl" in snappy
    assert "name drone;" in snappy
    assert "drone\n" in velocity
    assert "drone\n" in pressure


def test_report_includes_trace_events_assumptions_and_warnings(tmp_path: Path) -> None:
    geometry_file = tmp_path / "drone.stl"
    _write_binary_stl(geometry_file)
    output_dir = tmp_path / "case"

    spec = build_case_spec(
        case_name="case",
        geometry=build_single_stl_geometry(geometry_file),
        velocity_mps=10.0,
    )
    report = write_openfoam_case(spec, output_dir)

    assert report.assumptions
    assert report.warnings
    assert "ValidationRun" in [event.event_type for event in report.trace_events]
    assert report.validation_checks


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

