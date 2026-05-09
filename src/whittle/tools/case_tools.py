"""Typed case construction helpers."""

from __future__ import annotations

from whittle.models.case_spec import BoundaryConditionPlan, SimulationCaseSpec
from whittle.models.geometry import DroneGeometrySpec


def build_case_spec(
    *,
    case_name: str,
    geometry: DroneGeometrySpec,
    velocity_mps: float,
    max_iterations: int = 500,
    write_interval: int = 100,
) -> SimulationCaseSpec:
    """Build a conservative V0 external-aero case spec from typed geometry."""

    assumptions = [
        "Steady incompressible external aerodynamics.",
        "Geometry is used as-is; no FreeCAD preprocessing, cleanup, splitting, or decimation.",
        "No MRF, actuator disk force source, or rotor-resolved CFD in V0.",
        "Sea-level air is represented with nu=1.5e-05 m^2/s.",
        "Generated OpenFOAM files are educational and not yet mesh-quality validated.",
    ]
    if geometry.geometry_mode == "surface_set":
        assumptions.append(
            "Legacy split BoxQuadcopterCase surfaces are used as first-run geometry."
        )
    else:
        assumptions.append("Single STL is treated as one no-slip drone wall patch.")

    boundary_plan = BoundaryConditionPlan(
        walls=geometry.patch_names,
        reference_velocity_mps=velocity_mps,
        notes=[
            "Inlet uses fixed velocity.",
            "Outlet uses fixed kinematic pressure and zero-gradient velocity.",
            "Top, bottom, and side patches use slip/zero-gradient farfield-style conditions.",
        ],
    )

    return SimulationCaseSpec(
        case_name=case_name,
        geometry=geometry,
        boundary_conditions=boundary_plan,
        reference_velocity_mps=velocity_mps,
        max_iterations=max_iterations,
        write_interval=write_interval,
        assumptions=assumptions,
    )
