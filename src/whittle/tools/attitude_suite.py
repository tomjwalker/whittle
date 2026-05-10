"""Generate the B/C attitude smoke-case suite."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from whittle.models.geometry import DroneGeometrySpec
from whittle.models.reports import CaseSetupReport
from whittle.openfoam.case_writer import write_openfoam_case
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_legacy_box_geometry


@dataclass(frozen=True)
class AttitudeSmokeCase:
    """One deterministic smoke case in the B/C progression."""

    directory_name: str
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    yaw_deg: float = 0.0


ATTITUDE_SMOKE_CASES = (
    AttitudeSmokeCase("legacy_box_mrf_smoke"),
    AttitudeSmokeCase("legacy_box_mrf_pitch10_smoke", pitch_deg=10.0),
    AttitudeSmokeCase("legacy_box_mrf_roll10_smoke", roll_deg=10.0),
    AttitudeSmokeCase("legacy_box_mrf_yaw10_smoke", yaw_deg=10.0),
    AttitudeSmokeCase("legacy_box_mrf_combined_smoke", roll_deg=5.0, pitch_deg=10.0, yaw_deg=10.0),
)


def write_attitude_smoke_suite(
    output_root: Path,
    *,
    velocity_mps: float = 5.0,
    mrf_omega_rad_s: float = 1000.0,
    max_iterations: int = 5,
    write_interval: int = 5,
    geometry: DroneGeometrySpec | None = None,
) -> list[CaseSetupReport]:
    """Write B/C smoke cases for no attitude, pitch, roll, yaw, and combined attitude."""

    geometry = geometry or build_legacy_box_geometry()
    reports: list[CaseSetupReport] = []
    for smoke_case in ATTITUDE_SMOKE_CASES:
        spec = build_case_spec(
            case_name=smoke_case.directory_name,
            geometry=geometry,
            velocity_mps=velocity_mps,
            max_iterations=max_iterations,
            write_interval=write_interval,
            rotor_model="mrf",
            mrf_omega_rad_s=mrf_omega_rad_s,
            roll_deg=smoke_case.roll_deg,
            pitch_deg=smoke_case.pitch_deg,
            yaw_deg=smoke_case.yaw_deg,
        )
        reports.append(write_openfoam_case(spec, output_root / smoke_case.directory_name))
    return reports
