"""Simulation case domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from whittle.models.geometry import DroneGeometrySpec
from whittle.models.rotors import MRFZoneSpec


class BoundaryConditionPlan(BaseModel):
    """OpenFOAM boundary patch intent for the generated case."""

    inlet: str = "inlet"
    outlet: str = "outlet"
    farfield: list[str] = Field(default_factory=lambda: ["side1", "side2", "top", "bottom"])
    walls: list[str]
    reference_velocity_mps: float
    notes: list[str] = Field(default_factory=list)


class SimulationCaseSpec(BaseModel):
    """Typed state for a drone external-aero OpenFOAM case setup."""

    case_name: str
    geometry: DroneGeometrySpec
    boundary_conditions: BoundaryConditionPlan
    fluid: str = "air"
    flow_regime: str = "steady_incompressible_external"
    reference_velocity_mps: float
    angle_of_attack_deg: float = 0.0
    yaw_angle_deg: float = 0.0
    roll_angle_deg: float = 0.0
    pitch_angle_deg: float = 0.0
    rotor_model: Literal["none", "actuator_disk_placeholder", "mrf"] = "none"
    mrf_zones: list[MRFZoneSpec] = Field(default_factory=list)
    solver_family: str = "simpleFoam"
    turbulence_model: str = "kOmegaSST"
    mesh_strategy: str = "blockMesh background mesh with snappyHexMesh surface snapping"
    kinematic_viscosity_m2_s: float = 1.5e-5
    air_density_kg_m3: float = 1.225
    max_iterations: int = 500
    write_interval: int = 100
    transform_origin_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    missing_information: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    validation_checks: list[str] = Field(default_factory=list)
