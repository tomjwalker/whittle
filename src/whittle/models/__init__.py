"""Typed domain models for Whittle."""

from whittle.models.case_spec import BoundaryConditionPlan, SimulationCaseSpec
from whittle.models.geometry import DroneGeometrySpec, GeometrySurfaceSpec, StlMetadata
from whittle.models.openfoam import OpenFOAMCaseFiles
from whittle.models.reports import CaseSetupReport, TraceEvent

__all__ = [
    "BoundaryConditionPlan",
    "CaseSetupReport",
    "DroneGeometrySpec",
    "GeometrySurfaceSpec",
    "OpenFOAMCaseFiles",
    "SimulationCaseSpec",
    "StlMetadata",
    "TraceEvent",
]

