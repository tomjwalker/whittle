"""Typed domain models for Whittle."""

from whittle.models.agent import PlanningAgentResponse
from whittle.models.case_spec import BoundaryConditionPlan, SimulationCaseSpec
from whittle.models.geometry import DroneGeometrySpec, GeometrySurfaceSpec, StlMetadata
from whittle.models.openfoam import OpenFOAMCaseFiles
from whittle.models.planning import PhysicsEnvelope, ScenarioPlan
from whittle.models.reports import CaseSetupReport, TraceEvent
from whittle.models.rotors import MRFZoneSpec, RotorAssemblySpec, RotorDiskSourceSpec

__all__ = [
    "BoundaryConditionPlan",
    "CaseSetupReport",
    "DroneGeometrySpec",
    "GeometrySurfaceSpec",
    "MRFZoneSpec",
    "RotorDiskSourceSpec",
    "OpenFOAMCaseFiles",
    "PhysicsEnvelope",
    "PlanningAgentResponse",
    "RotorAssemblySpec",
    "ScenarioPlan",
    "SimulationCaseSpec",
    "StlMetadata",
    "TraceEvent",
]
