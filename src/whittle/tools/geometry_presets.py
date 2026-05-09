"""Geometry preset builders for Whittle V0."""

from __future__ import annotations

from pathlib import Path

from whittle.models.geometry import DroneGeometrySpec, GeometrySurfaceSpec
from whittle.tools.stl_tools import read_stl_metadata

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LEGACY_ASSET_ROOT = PROJECT_ROOT / "assets" / "legacy_box_quadcopter" / "triSurface"

LEGACY_BOX_SURFACES = (
    ("drone_model_box__body.stl", "drone_body", "body"),
    ("drone_model_box__prop_fr.stl", "propeller_fr", "propeller"),
    ("drone_model_box__prop_br.stl", "propeller_br", "propeller"),
    ("drone_model_box__prop_fl.stl", "propeller_fl", "propeller"),
    ("drone_model_box__prop_bl.stl", "propeller_bl", "propeller"),
)


def build_legacy_box_geometry(asset_root: Path | None = None) -> DroneGeometrySpec:
    """Build the known-good split-surface legacy quadcopter geometry spec."""

    root = Path(asset_root) if asset_root else LEGACY_ASSET_ROOT
    surfaces = [
        GeometrySurfaceSpec(
            source_path=root / file_name,
            target_file_name=file_name,
            patch_name=patch_name,
            role=role,
            scale_to_m=1.0,
            metadata=read_stl_metadata(root / file_name),
        )
        for file_name, patch_name, role in LEGACY_BOX_SURFACES
    ]

    return DroneGeometrySpec(
        name="legacy_box_quadcopter",
        geometry_mode="surface_set",
        surfaces=surfaces,
        units="m",
        scale_to_m=1.0,
        notes=[
            "Known-good split surfaces copied from prior Isembard/OpenFOAM BoxQuadcopterCase.",
            "Used as Whittle V0 first-run geometry before returning to the monolithic hex STL.",
        ],
    )


def build_single_stl_geometry(geometry_path: Path, patch_name: str = "drone") -> DroneGeometrySpec:
    """Build a single-STL geometry spec for the local hexacopter target."""

    geometry_path = Path(geometry_path)
    metadata = read_stl_metadata(geometry_path)
    surface = GeometrySurfaceSpec(
        source_path=geometry_path,
        target_file_name=geometry_path.name,
        patch_name=patch_name,
        role="drone",
        scale_to_m=metadata.scale_to_m,
        metadata=metadata,
    )
    return DroneGeometrySpec(
        name=geometry_path.stem,
        geometry_mode="single_stl",
        surfaces=[surface],
        units=metadata.inferred_units,
        scale_to_m=metadata.scale_to_m,
        notes=[
            "Single STL used as one OpenFOAM wall patch.",
            "No FreeCAD cleanup, splitting, or decimation is applied in V0.",
        ],
    )

