"""Deterministic OpenFOAM case writer for Whittle V0."""

from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

from whittle.models.case_spec import SimulationCaseSpec
from whittle.models.reports import CaseSetupReport, TraceEvent
from whittle.tools.validation_tools import validate_case_spec, validate_required_files

INITIAL_FIELDS = ("U", "p", "k", "omega", "nut")
SYSTEM_FILES = ("controlDict", "blockMeshDict", "snappyHexMeshDict", "fvSchemes", "fvSolution")
CONSTANT_FILES = ("transportProperties", "turbulenceProperties")


def write_openfoam_case(spec: SimulationCaseSpec, output_dir: Path) -> CaseSetupReport:
    """Write a V0 OpenFOAM case and return a human-reviewable report."""

    case_dir = Path(output_dir)
    zero_dir = case_dir / "0"
    constant_dir = case_dir / "constant"
    tri_surface_dir = constant_dir / "triSurface"
    system_dir = case_dir / "system"

    for directory in (zero_dir, tri_surface_dir, system_dir):
        directory.mkdir(parents=True, exist_ok=True)

    trace_events = [
        TraceEvent(
            event_type="RequestReceived",
            message="Deterministic write-case request received.",
            data={"case_name": spec.case_name},
        ),
        TraceEvent(
            event_type="GeometryResolved",
            message="Geometry surfaces resolved into OpenFOAM patch names.",
            data={
                "geometry_mode": spec.geometry.geometry_mode,
                "patches": spec.geometry.patch_names,
            },
        ),
        TraceEvent(
            event_type="CaseSpecBuilt",
            message="Typed SimulationCaseSpec is ready for file generation.",
            data={"solver": spec.solver_family, "turbulence_model": spec.turbulence_model},
        ),
        TraceEvent(
            event_type="AssumptionsRecorded",
            message="Case assumptions recorded for human review.",
            data={"assumption_count": len(spec.assumptions)},
        ),
        TraceEvent(
            event_type="OpenFOAMFilesPlanned",
            message="OpenFOAM case directory and required files planned.",
            data={"case_dir": str(case_dir)},
        ),
    ]

    files_written: list[str] = []
    for surface in spec.geometry.surfaces:
        if not surface.source_path.exists():
            continue
        destination = tri_surface_dir / surface.target_file_name
        if surface.source_path.resolve() != destination.resolve():
            shutil.copy2(surface.source_path, destination)
        files_written.append(_relative(case_dir, destination))

    _write(case_dir, "0/U", _velocity_field(spec), files_written)
    _write(case_dir, "0/p", _pressure_field(spec), files_written)
    _write(case_dir, "0/k", _k_field(spec), files_written)
    _write(case_dir, "0/omega", _omega_field(spec), files_written)
    _write(case_dir, "0/nut", _nut_field(spec), files_written)
    _write(
        case_dir,
        "constant/transportProperties",
        _transport_properties(spec),
        files_written,
    )
    _write(
        case_dir,
        "constant/turbulenceProperties",
        _turbulence_properties(spec),
        files_written,
    )
    _write(case_dir, "system/controlDict", _control_dict(spec), files_written)
    _write(case_dir, "system/blockMeshDict", _block_mesh_dict(spec), files_written)
    _write(case_dir, "system/snappyHexMeshDict", _snappy_hex_mesh_dict(spec), files_written)
    _write(case_dir, "system/fvSchemes", _fv_schemes(), files_written)
    _write(case_dir, "system/fvSolution", _fv_solution(), files_written)
    _write(case_dir, "Allrun", _allrun(), files_written)
    _write(case_dir, "Allclean", _allclean(), files_written)

    for script_name in ("Allrun", "Allclean"):
        try:
            os.chmod(case_dir / script_name, 0o755)
        except OSError:
            pass

    foam_file = case_dir / f"{spec.case_name}.foam"
    foam_file.touch()
    files_written.append(_relative(case_dir, foam_file))

    spec_checks, warnings, missing = validate_case_spec(spec)
    expected_files = _expected_files(spec)
    file_checks, missing_files = validate_required_files(case_dir, expected_files)
    missing.extend(missing_files)
    validation_checks = spec_checks + file_checks
    spec.validation_checks = validation_checks
    spec.missing_information = missing

    trace_events.extend(
        [
            TraceEvent(
                event_type="FilesWritten",
                message="OpenFOAM case files written.",
                data={"file_count": len(files_written)},
            ),
            TraceEvent(
                event_type="ValidationRun",
                message="Deterministic validation checks completed.",
                data={"check_count": len(validation_checks), "missing_count": len(missing)},
            ),
            TraceEvent(
                event_type="HumanReviewNeeded",
                message="Generated case should be reviewed before OpenFOAM execution.",
                data={"can_run": not missing},
            ),
        ]
    )

    report = CaseSetupReport(
        case_name=spec.case_name,
        spec=spec,
        files_written=files_written + ["case_report.json"],
        assumptions=spec.assumptions,
        warnings=warnings,
        missing_information=missing,
        can_run=not missing,
        why_not_run="; ".join(missing) if missing else None,
        recommended_next_steps=[
            "Inspect generated OpenFOAM dictionaries and patch names.",
            "Copy or open the case under WSL OpenFOAM when ready.",
            "Run blockMesh, snappyHexMesh -overwrite, checkMesh, then simpleFoam manually.",
        ],
        trace_events=trace_events,
        validation_checks=validation_checks,
    )

    report_path = case_dir / "case_report.json"
    report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report


def _expected_files(spec: SimulationCaseSpec) -> list[str]:
    return [
        "0/U",
        "0/p",
        "0/k",
        "0/omega",
        "0/nut",
        "constant/transportProperties",
        "constant/turbulenceProperties",
        "system/controlDict",
        "system/blockMeshDict",
        "system/snappyHexMeshDict",
        "system/fvSchemes",
        "system/fvSolution",
        "Allrun",
        "Allclean",
        f"{spec.case_name}.foam",
    ]


def _write(case_dir: Path, relative_path: str, content: str, files_written: list[str]) -> None:
    path = case_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    files_written.append(relative_path)


def _relative(case_dir: Path, path: Path) -> str:
    return path.relative_to(case_dir).as_posix()


def _header(foam_class: str, obj: str, location: str | None = None) -> str:
    location_line = f'    location    "{location}";\n' if location else ""
    return (
        "/*--------------------------------*- C++ -*----------------------------------*\\\n"
        "| =========                 |                                                 |\n"
        "| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |\n"
        "|  \\\\    /   O peration     | Version:  v2012                                 |\n"
        "|   \\\\  /    A nd           |                                                 |\n"
        "|    \\\\/     M anipulation  |                                                 |\n"
        "\\*---------------------------------------------------------------------------*/\n"
        "FoamFile\n"
        "{\n"
        "    version     2.0;\n"
        "    format      ascii;\n"
        f"    class       {foam_class};\n"
        f"{location_line}"
        f"    object      {obj};\n"
        "}\n"
        "// ************************************************************************* //\n\n"
    )


def _velocity_field(spec: SimulationCaseSpec) -> str:
    u = spec.reference_velocity_mps
    walls = _wall_patch_blocks(spec, "noSlip")
    farfield = _patch_blocks(spec.boundary_conditions.farfield, "slip")
    return (
        _header("volVectorField", "U", "0")
        + "dimensions      [0 1 -1 0 0 0 0];\n\n"
        + f"internalField   uniform ({u:g} 0 0);\n\n"
        + "boundaryField\n{\n"
        + _patch_block(spec.boundary_conditions.inlet, "fixedValue", f"uniform ({u:g} 0 0)")
        + _patch_block(spec.boundary_conditions.outlet, "zeroGradient")
        + walls
        + farfield
        + "}\n\n// ************************************************************************* //\n"
    )


def _pressure_field(spec: SimulationCaseSpec) -> str:
    walls = _wall_patch_blocks(spec, "zeroGradient")
    farfield = _patch_blocks(spec.boundary_conditions.farfield, "zeroGradient")
    return (
        _header("volScalarField", "p", "0")
        + "dimensions      [0 2 -2 0 0 0 0];\n\n"
        + "internalField   uniform 0;\n\n"
        + "boundaryField\n{\n"
        + _patch_block(spec.boundary_conditions.inlet, "zeroGradient")
        + _patch_block(spec.boundary_conditions.outlet, "fixedValue", "uniform 0")
        + walls
        + farfield
        + "}\n\n// ************************************************************************* //\n"
    )


def _k_field(spec: SimulationCaseSpec) -> str:
    k_value = _turbulent_kinetic_energy(spec.reference_velocity_mps)
    walls = _wall_patch_blocks(spec, "kqRWallFunction", f"uniform {k_value:.6g}")
    farfield = _patch_blocks(spec.boundary_conditions.farfield, "zeroGradient")
    return (
        _header("volScalarField", "k", "0")
        + "dimensions      [0 2 -2 0 0 0 0];\n\n"
        + f"internalField   uniform {k_value:.6g};\n\n"
        + "boundaryField\n{\n"
        + _patch_block(spec.boundary_conditions.inlet, "fixedValue", f"uniform {k_value:.6g}")
        + _patch_block(spec.boundary_conditions.outlet, "zeroGradient")
        + walls
        + farfield
        + "}\n\n// ************************************************************************* //\n"
    )


def _omega_field(spec: SimulationCaseSpec) -> str:
    omega_value = _omega(spec.reference_velocity_mps)
    walls = _wall_patch_blocks(spec, "omegaWallFunction", f"uniform {omega_value:.6g}")
    farfield = _patch_blocks(spec.boundary_conditions.farfield, "zeroGradient")
    return (
        _header("volScalarField", "omega", "0")
        + "dimensions      [0 0 -1 0 0 0 0];\n\n"
        + f"internalField   uniform {omega_value:.6g};\n\n"
        + "boundaryField\n{\n"
        + _patch_block(
            spec.boundary_conditions.inlet,
            "fixedValue",
            f"uniform {omega_value:.6g}",
        )
        + _patch_block(spec.boundary_conditions.outlet, "zeroGradient")
        + walls
        + farfield
        + "}\n\n// ************************************************************************* //\n"
    )


def _nut_field(spec: SimulationCaseSpec) -> str:
    walls = _wall_patch_blocks(spec, "nutkWallFunction", "uniform 0")
    farfield = _patch_blocks(spec.boundary_conditions.farfield, "calculated", "uniform 0")
    return (
        _header("volScalarField", "nut", "0")
        + "dimensions      [0 2 -1 0 0 0 0];\n\n"
        + "internalField   uniform 0;\n\n"
        + "boundaryField\n{\n"
        + _patch_block(spec.boundary_conditions.inlet, "calculated", "uniform 0")
        + _patch_block(spec.boundary_conditions.outlet, "calculated", "uniform 0")
        + walls
        + farfield
        + "}\n\n// ************************************************************************* //\n"
    )


def _transport_properties(spec: SimulationCaseSpec) -> str:
    return (
        _header("dictionary", "transportProperties")
        + "transportModel  Newtonian;\n\n"
        + f"nu              {spec.kinematic_viscosity_m2_s:.6g};\n\n"
        + "// ************************************************************************* //\n"
    )


def _turbulence_properties(spec: SimulationCaseSpec) -> str:
    return (
        _header("dictionary", "turbulenceProperties")
        + "simulationType RAS;\n\n"
        + "RAS\n{\n"
        + f"    RASModel        {spec.turbulence_model};\n"
        + "    turbulence      on;\n"
        + "    printCoeffs     on;\n"
        + "}\n\n// ************************************************************************* //\n"
    )


def _control_dict(spec: SimulationCaseSpec) -> str:
    patches = " ".join(spec.boundary_conditions.walls)
    return (
        _header("dictionary", "controlDict")
        + f"application     {spec.solver_family};\n\n"
        + "startFrom       startTime;\n"
        + "startTime       0;\n"
        + "stopAt          endTime;\n"
        + f"endTime         {spec.max_iterations};\n"
        + "deltaT          1;\n\n"
        + "writeControl    timeStep;\n"
        + f"writeInterval   {spec.write_interval};\n"
        + "writePrecision  10;\n"
        + "runTimeModifiable true;\n\n"
        + "functions\n{\n"
        + "    forces\n    {\n"
        + "        type            forces;\n"
        + '        libs            ("libforces.so");\n'
        + f"        patches         ({patches});\n"
        + "        rho             rhoInf;\n"
        + f"        rhoInf          {spec.air_density_kg_m3:.6g};\n"
        + "        CofR            (0 0 0);\n"
        + "        log             yes;\n"
        + "        writeControl    timeStep;\n"
        + "        writeInterval   1;\n"
        + "    }\n"
        + "}\n\n// ************************************************************************* //\n"
    )


def _block_mesh_dict(spec: SimulationCaseSpec) -> str:
    if spec.geometry.name == "legacy_box_quadcopter":
        x_min, x_max = -0.75, 0.75
        y_min, y_max = -0.75, 0.75
        z_min, z_max = -0.5, 0.5
        cells = (120, 120, 80)
    else:
        length = _characteristic_length_m(spec)
        x_min, x_max = -5.0 * length, 10.0 * length
        y_min, y_max = -5.0 * length, 5.0 * length
        z_min, z_max = -5.0 * length, 5.0 * length
        cells = (80, 60, 60)

    return (
        _header("dictionary", "blockMeshDict")
        + "scale 1.0;\n\n"
        + "vertices\n(\n"
        + f"    ({x_min:g} {y_min:g} {z_min:g})\n"
        + f"    ({x_max:g} {y_min:g} {z_min:g})\n"
        + f"    ({x_max:g} {y_max:g} {z_min:g})\n"
        + f"    ({x_min:g} {y_max:g} {z_min:g})\n"
        + f"    ({x_min:g} {y_min:g} {z_max:g})\n"
        + f"    ({x_max:g} {y_min:g} {z_max:g})\n"
        + f"    ({x_max:g} {y_max:g} {z_max:g})\n"
        + f"    ({x_min:g} {y_max:g} {z_max:g})\n"
        + ");\n\n"
        + "blocks\n(\n"
        + f"    hex (0 1 2 3 4 5 6 7) ({cells[0]} {cells[1]} {cells[2]}) "
        + "simpleGrading (1 1 1)\n"
        + ");\n\n"
        + "edges\n(\n);\n\n"
        + "boundary\n(\n"
        + _block_patch("inlet", "patch", "(0 4 7 3)")
        + _block_patch("outlet", "patch", "(1 2 6 5)")
        + _block_patch("side1", "patch", "(0 1 5 4)")
        + _block_patch("side2", "patch", "(3 7 6 2)")
        + _block_patch("bottom", "patch", "(0 3 2 1)")
        + _block_patch("top", "patch", "(4 5 6 7)")
        + ");\n\n"
        + "mergePatchPairs\n(\n);\n\n"
        + "// ************************************************************************* //\n"
    )


def _snappy_hex_mesh_dict(spec: SimulationCaseSpec) -> str:
    geometry_entries = []
    refinement_entries = []
    for surface in spec.geometry.surfaces:
        scale_line = f"        scale {surface.scale_to_m:g};\n" if surface.scale_to_m != 1.0 else ""
        geometry_entries.append(
            f"    {surface.target_file_name}\n"
            "    {\n"
            "        type triSurfaceMesh;\n"
            f"        name {surface.patch_name};\n"
            f"{scale_line}"
            "    }\n"
        )
        level = "(4 5)" if surface.role == "propeller" else "(3 4)"
        refinement_entries.append(
            f"        {surface.patch_name}\n"
            "        {\n"
            f"            level {level};\n"
            "            patchInfo\n"
            "            {\n"
            "                type wall;\n"
            "            }\n"
            "        }\n"
        )

    return (
        _header("dictionary", "snappyHexMeshDict")
        + "castellatedMesh true;\n"
        + "snap            true;\n"
        + "addLayers       false;\n\n"
        + "geometry\n{\n"
        + "\n".join(geometry_entries)
        + "}\n\n"
        + "castellatedMeshControls\n{\n"
        + "    maxLocalCells   100000;\n"
        + "    maxGlobalCells  2000000;\n"
        + "    minRefinementCells 10;\n"
        + "    maxLoadUnbalance 0.10;\n"
        + "    nCellsBetweenLevels 3;\n\n"
        + "    features\n"
        + "    (\n"
        + "    );\n\n"
        + "    refinementSurfaces\n"
        + "    {\n"
        + "\n".join(refinement_entries)
        + "    }\n\n"
        + "    refinementRegions\n"
        + "    {\n"
        + "    }\n\n"
        + "    resolveFeatureAngle 25;\n"
        + "    locationInMesh (0 0 0.1);\n"
        + "    allowFreeStandingZoneFaces true;\n"
        + "}\n\n"
        + "snapControls\n{\n"
        + "    nSmoothPatch 3;\n"
        + "    tolerance    2.0;\n"
        + "    nSolveIter   30;\n"
        + "    nRelaxIter   5;\n"
        + "    nFeatureSnapIter 10;\n"
        + "    implicitFeatureSnap true;\n"
        + "    explicitFeatureSnap false;\n"
        + "    multiRegionFeatureSnap false;\n"
        + "}\n\n"
        + "addLayersControls\n{\n"
        + "}\n\n"
        + "meshQualityControls\n{\n"
        + "    maxNonOrtho 65;\n"
        + "    maxBoundarySkewness 20;\n"
        + "    maxInternalSkewness 4;\n"
        + "    maxConcave 80;\n"
        + "    minVol 1e-13;\n"
        + "    minTetQuality 1e-15;\n"
        + "    minArea -1;\n"
        + "    minTwist 0.02;\n"
        + "    minDeterminant 0.001;\n"
        + "    minFaceWeight 0.02;\n"
        + "    minVolRatio 0.01;\n"
        + "    minTriangleTwist -1;\n"
        + "    nSmoothScale 4;\n"
        + "    errorReduction 0.75;\n"
        + "}\n\n"
        + "mergeTolerance 1e-6;\n\n"
        + "// ************************************************************************* //\n"
    )


def _fv_schemes() -> str:
    return (
        _header("dictionary", "fvSchemes")
        + "ddtSchemes\n{\n    default         steadyState;\n}\n\n"
        + "gradSchemes\n{\n    default         Gauss linear;\n}\n\n"
        + "divSchemes\n{\n"
        + "    default         none;\n"
        + "    div(phi,U)      Gauss upwind;\n"
        + "    div(phi,k)      Gauss upwind;\n"
        + "    div(phi,omega)  Gauss upwind;\n"
        + "    div(phi,nut)    Gauss upwind;\n"
        + "    div((nuEff*dev2(T(grad(U))))) Gauss linear;\n"
        + "    div((nuEff*dev(T(grad(U))))) Gauss linear;\n"
        + "}\n\n"
        + "laplacianSchemes\n{\n    default         Gauss linear orthogonal;\n}\n\n"
        + "interpolationSchemes\n{\n    default         linear;\n}\n\n"
        + "snGradSchemes\n{\n    default         orthogonal;\n}\n\n"
        + "fluxRequired\n{\n    default         no;\n    p;\n}\n\n"
        + "wallDist\n{\n    method meshWave;\n}\n\n"
        + "// ************************************************************************* //\n"
    )


def _fv_solution() -> str:
    return (
        _header("dictionary", "fvSolution")
        + "solvers\n{\n"
        + _solver_block("p", "PCG", "DIC", "1e-06")
        + _solver_block("U", "PBiCGStab", "DILU", "1e-05")
        + _solver_block("k", "PBiCGStab", "DILU", "1e-05")
        + _solver_block("omega", "PBiCGStab", "DILU", "1e-05")
        + _solver_block("nut", "PBiCGStab", "DILU", "1e-05")
        + "}\n\n"
        + "SIMPLE\n{\n"
        + "    nNonOrthogonalCorrectors 0;\n"
        + "    consistent yes;\n"
        + "}\n\n"
        + "relaxationFactors\n{\n"
        + "    fields\n    {\n        p               0.3;\n    }\n\n"
        + "    equations\n    {\n"
        + "        U               0.7;\n"
        + "        k               0.7;\n"
        + "        omega           0.7;\n"
        + "        nut             0.7;\n"
        + "    }\n"
        + "}\n\n// ************************************************************************* //\n"
    )


def _allrun() -> str:
    return (
        "#!/bin/sh\n"
        'cd "${0%/*}" || exit\n'
        '. ${WM_PROJECT_DIR:?}/bin/tools/RunFunctions\n\n'
        "runApplication blockMesh\n"
        "runApplication snappyHexMesh -overwrite\n"
        "runApplication checkMesh\n"
        "runApplication simpleFoam\n"
    )


def _allclean() -> str:
    return (
        "#!/bin/sh\n"
        'cd "${0%/*}" || exit\n'
        '. ${WM_PROJECT_DIR:?}/bin/tools/CleanFunctions\n\n'
        "cleanCase\n"
        "rm -f log.*\n"
    )


def _patch_blocks(patches: list[str], patch_type: str, value: str | None = None) -> str:
    return "".join(_patch_block(patch, patch_type, value) for patch in patches)


def _wall_patch_blocks(spec: SimulationCaseSpec, patch_type: str, value: str | None = None) -> str:
    return _patch_blocks(spec.boundary_conditions.walls, patch_type, value)


def _patch_block(name: str, patch_type: str, value: str | None = None) -> str:
    value_line = f"        value           {value};\n" if value is not None else ""
    return (
        f"    {name}\n"
        "    {\n"
        f"        type            {patch_type};\n"
        f"{value_line}"
        "    }\n\n"
    )


def _block_patch(name: str, patch_type: str, face: str) -> str:
    return (
        f"    {name}\n"
        "    {\n"
        f"        type {patch_type};\n"
        "        faces\n"
        "        (\n"
        f"            {face}\n"
        "        );\n"
        "    }\n"
    )


def _solver_block(field: str, solver: str, preconditioner: str, tolerance: str) -> str:
    return (
        f"    {field}\n"
        "    {\n"
        f"        solver          {solver};\n"
        f"        preconditioner  {preconditioner};\n"
        f"        tolerance       {tolerance};\n"
        "        relTol          0;\n"
        "    }\n\n"
    )


def _turbulent_kinetic_energy(velocity_mps: float) -> float:
    intensity = 0.05
    return 1.5 * (intensity * velocity_mps) ** 2


def _omega(velocity_mps: float) -> float:
    mixing_length = 0.1
    k_value = _turbulent_kinetic_energy(velocity_mps)
    return math.sqrt(k_value) / (0.09**0.25 * mixing_length)


def _characteristic_length_m(spec: SimulationCaseSpec) -> float:
    lengths: list[float] = []
    for surface in spec.geometry.surfaces:
        if surface.metadata and surface.metadata.dimensions_raw:
            raw_length = max(surface.metadata.dimensions_raw)
            lengths.append(max(0.1, raw_length * surface.scale_to_m))
    return max(lengths, default=0.5)
