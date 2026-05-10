"""Typed case construction helpers."""

from __future__ import annotations

from typing import Literal

from whittle.models.case_spec import BoundaryConditionPlan, SimulationCaseSpec
from whittle.models.geometry import DroneGeometrySpec, Vector3
from whittle.tools.rotor_presets import build_legacy_box_mrf_zones


def build_case_spec(
    *,
    case_name: str,
    geometry: DroneGeometrySpec,
    velocity_mps: float,
    max_iterations: int = 500,
    write_interval: int = 100,
    rotor_model: Literal["none", "actuator_disk_placeholder", "mrf"] = "none",
    mrf_omega_rad_s: float = 1000.0,
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
    transform_origin_m: Vector3 = (0.0, 0.0, 0.0),
) -> SimulationCaseSpec:
    """Build a conservative V0 external-aero case spec from typed geometry."""

    assumptions = [
        "Steady incompressible external aerodynamics.",
        "Geometry is used as-is; no FreeCAD preprocessing, cleanup, splitting, or decimation.",
        "Sea-level air is represented with nu=1.5e-05 m^2/s.",
        "Generated OpenFOAM files are educational and not yet mesh-quality validated.",
        "Legacy CAD pose is treated as roll=0, pitch=0, yaw=0 even though it has baked-in pitch.",
    ]
    mrf_zones = []
    missing_information: list[str] = []
    if rotor_model == "mrf":
        if geometry.name == "legacy_box_quadcopter":
            assumptions.append(
                "MRF rotor zones use legacy BoxQuadcopterCase centres, axes, and cell-zone names."
            )
            mrf_zones = build_legacy_box_mrf_zones(
                omega_rad_s=mrf_omega_rad_s,
                roll_deg=roll_deg,
                pitch_deg=pitch_deg,
                yaw_deg=yaw_deg,
                origin_m=transform_origin_m,
            )
        else:
            missing_information.append(
                "MRF rotor model is currently supported only for legacy-box."
            )
    elif rotor_model == "actuator_disk_placeholder":
        assumptions.append("Actuator disk placeholder requested; no force source is written yet.")
    else:
        assumptions.append(
            "No MRF, actuator disk force source, or rotor-resolved CFD in this case."
        )

    if any(abs(value) > 1e-12 for value in (roll_deg, pitch_deg, yaw_deg)):
        assumptions.append(
            "Geometry and rotor zones are transformed as one rigid assembly from the legacy pose."
        )

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
        roll_angle_deg=roll_deg,
        pitch_angle_deg=pitch_deg,
        yaw_angle_deg=yaw_deg,
        rotor_model=rotor_model,
        mrf_zones=mrf_zones,
        max_iterations=max_iterations,
        write_interval=write_interval,
        transform_origin_m=transform_origin_m,
        missing_information=missing_information,
        assumptions=assumptions,
    )
