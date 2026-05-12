"""Deterministic validation for V0 case specs and generated files."""

from __future__ import annotations

from pathlib import Path

from whittle.models.case_spec import SimulationCaseSpec
from whittle.tools.physics_envelope import validate_physics_envelope


def validate_case_spec(spec: SimulationCaseSpec) -> tuple[list[str], list[str], list[str]]:
    """Return validation checks, warnings, and missing information."""

    checks: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    if spec.reference_velocity_mps < 0:
        missing.append("reference_velocity_mps must not be negative.")
    elif spec.reference_velocity_mps == 0 and not _is_zero_freestream_rotor_proxy(spec):
        missing.append("reference_velocity_mps must be positive.")
    else:
        if spec.reference_velocity_mps == 0:
            checks.append(
                "Reference velocity is zero for a static/differential MRF proxy "
                "or rotor-disk proxy case."
            )
        else:
            checks.append("Reference velocity is positive.")
        envelope_checks, envelope_warnings, envelope_missing = validate_physics_envelope(spec)
        checks.extend(envelope_checks)
        warnings.extend(envelope_warnings)
        missing.extend(envelope_missing)

    if not spec.geometry.surfaces:
        missing.append("At least one geometry surface is required.")
    else:
        checks.append("Geometry includes at least one surface.")

    patch_names = spec.geometry.patch_names
    if len(patch_names) != len(set(patch_names)):
        missing.append("Geometry patch names must be unique.")
    else:
        checks.append("Geometry patch names are unique.")

    if spec.rotor_model == "mrf":
        if spec.mrf_zones:
            checks.append("MRF rotor model includes at least one zone.")
            cell_zones = [zone.cell_zone for zone in spec.mrf_zones]
            if len(cell_zones) != len(set(cell_zones)):
                missing.append("MRF cell-zone names must be unique.")
            else:
                checks.append("MRF cell-zone names are unique.")
        else:
            missing.append("MRF rotor model requested but no MRF zones were defined.")
    elif spec.rotor_model == "rotor_disk":
        if spec.rotor_disk_sources:
            checks.append("Rotor-disk model includes at least one fvOptions source.")
            cell_zones = [source.cell_zone for source in spec.rotor_disk_sources]
            if len(cell_zones) != len(set(cell_zones)):
                missing.append("Rotor-disk cell-zone names must be unique.")
            else:
                checks.append("Rotor-disk cell-zone names are unique.")
        else:
            missing.append("Rotor-disk model requested but no rotor-disk sources were defined.")

    for surface in spec.geometry.surfaces:
        if not surface.source_path.exists():
            missing.append(f"Geometry file does not exist: {surface.source_path}")
        else:
            checks.append(f"Geometry file exists: {surface.source_path.name}")

        if surface.metadata:
            warnings.extend(surface.metadata.warnings)
            if surface.metadata.triangle_count and surface.metadata.triangle_count > 1_000_000:
                warnings.append(
                    f"{surface.source_path.name} has more than one million triangles; "
                    "meshing may be slow."
                )

    warnings.extend(spec.missing_information)
    warnings.append("OpenFOAM case has not been run through blockMesh/snappyHexMesh/checkMesh.")
    if spec.rotor_model == "mrf":
        warnings.append(
            "MRF zones are generated from legacy reference data and require mesh validation."
        )
    elif spec.rotor_model == "rotor_disk":
        warnings.append(
            "Rotor-disk fvOptions are heuristic source terms; check sign, source strength, "
            "and downwash in ParaView before trusting force numbers."
        )
    else:
        warnings.append(
            "MRF and actuator disk source terms are intentionally omitted in this case."
        )

    return checks, _deduplicate(warnings), _deduplicate(missing + spec.missing_information)


def validate_required_files(
    case_dir: Path,
    expected_files: list[str],
) -> tuple[list[str], list[str]]:
    """Check generated file presence."""

    checks: list[str] = []
    missing: list[str] = []
    for file_name in expected_files:
        path = case_dir / file_name
        if path.exists():
            checks.append(f"Generated {file_name}.")
        else:
            missing.append(f"Missing generated file: {file_name}")
    return checks, missing


def _deduplicate(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _is_zero_freestream_rotor_proxy(spec: SimulationCaseSpec) -> bool:
    return (
        spec.flow_regime
        in {
            "steady_incompressible_static_mrf_hover",
            "steady_incompressible_motion_proxy_mrf",
            "steady_incompressible_static_rotor_disk_hover",
            "steady_incompressible_motion_proxy_rotor_disk",
        }
        and spec.rotor_model in {"mrf", "rotor_disk"}
    )
