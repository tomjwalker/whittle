"""Rotor and MRF zone domain models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from whittle.models.geometry import Vector3


class MRFZoneSpec(BaseModel):
    """Multiple Reference Frame zone around one propeller."""

    name: str
    cell_zone: str
    cylinder_name: str
    centre_m: Vector3
    axis: Vector3
    radius_m: float
    height_m: float
    omega_rad_s: float
    source_patch: str | None = None
    notes: list[str] = Field(default_factory=list)


class RotorAssemblySpec(BaseModel):
    """Rotor modelling data attached to a simulation case."""

    model: str
    zones: list[MRFZoneSpec] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
