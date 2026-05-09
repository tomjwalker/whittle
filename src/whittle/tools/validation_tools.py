"""Deterministic validation for V0 case specs and generated files."""

from __future__ import annotations

from pathlib import Path

from whittle.models.case_spec import SimulationCaseSpec


def validate_case_spec(spec: SimulationCaseSpec) -> tuple[list[str], list[str], list[str]]:
    """Return validation checks, warnings, and missing information."""

    checks: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    if spec.reference_velocity_mps <= 0:
        missing.append("reference_velocity_mps must be positive.")
    else:
        checks.append("Reference velocity is positive.")

    if not spec.geometry.surfaces:
        missing.append("At least one geometry surface is required.")
    else:
        checks.append("Geometry includes at least one surface.")

    patch_names = spec.geometry.patch_names
    if len(patch_names) != len(set(patch_names)):
        missing.append("Geometry patch names must be unique.")
    else:
        checks.append("Geometry patch names are unique.")

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

    warnings.append("OpenFOAM case has not been run through blockMesh/snappyHexMesh/checkMesh.")
    warnings.append("MRF and actuator disk source terms are intentionally omitted in V0.")

    return checks, _deduplicate(warnings), missing


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
