"""Geometry and STL metadata models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Vector3 = tuple[float, float, float]


class StlMetadata(BaseModel):
    """Small metadata summary for an STL geometry input."""

    source_path: Path
    file_size_bytes: int
    format: Literal["binary", "ascii", "unknown"]
    triangle_count: int | None = None
    bounds_min: Vector3 | None = None
    bounds_max: Vector3 | None = None
    dimensions_raw: Vector3 | None = None
    inferred_units: Literal["m", "mm", "unknown"] = "unknown"
    scale_to_m: float = 1.0
    warnings: list[str] = Field(default_factory=list)


class GeometrySurfaceSpec(BaseModel):
    """One surface file and the OpenFOAM patch it should create."""

    source_path: Path
    target_file_name: str
    patch_name: str
    role: Literal["body", "propeller", "drone", "unknown"]
    scale_to_m: float = 1.0
    metadata: StlMetadata | None = None


class DroneGeometrySpec(BaseModel):
    """Geometry specification for either a single STL or split surface set."""

    name: str
    geometry_mode: Literal["single_stl", "surface_set"]
    surfaces: list[GeometrySurfaceSpec]
    units: Literal["m", "mm", "unknown"] = "unknown"
    scale_to_m: float = 1.0
    notes: list[str] = Field(default_factory=list)

    @property
    def patch_names(self) -> list[str]:
        return [surface.patch_name for surface in self.surfaces]

