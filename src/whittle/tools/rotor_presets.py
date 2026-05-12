"""Rotor presets for known legacy geometries."""

from __future__ import annotations

from collections.abc import Mapping

from whittle.models.geometry import Vector3
from whittle.models.rotors import MRFZoneSpec, RotorDiskSourceSpec
from whittle.tools.transform_tools import (
    normalise_vector,
    rotation_matrix,
    transform_mrf_zone,
    transform_rotor_disk_source,
)

LEGACY_BOX_BASE_AXIS: Vector3 = normalise_vector((-0.0872, 0.0, 0.9962))
LEGACY_BOX_MRF_RADIUS_M = 0.06
LEGACY_BOX_MRF_HEIGHT_M = 0.01

_LEGACY_BOX_ROTORS = (
    ("MRF1", "propFRZone", "rotorCylinder_fr", "propeller_fr", (-0.10517, 0.10412, 0.00749), 1.0),
    ("MRF2", "propBRZone", "rotorCylinder_br", "propeller_br", (0.10227, 0.10412, 0.02564), -1.0),
    ("MRF3", "propFLZone", "rotorCylinder_fl", "propeller_fl", (-0.10517, -0.10412, 0.00749), -1.0),
    ("MRF4", "propBLZone", "rotorCylinder_bl", "propeller_bl", (0.10227, -0.10412, 0.02564), 1.0),
)


def build_legacy_box_mrf_zones(
    *,
    omega_rad_s: float,
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
    origin_m: Vector3 = (0.0, 0.0, 0.0),
) -> list[MRFZoneSpec]:
    """Build MRF zones matching the prior BoxQuadcopterCase rotor layout."""

    omega_by_patch = {
        patch_name: direction * omega_rad_s
        for _, _, _, patch_name, _, direction in _LEGACY_BOX_ROTORS
    }
    return build_legacy_box_mrf_zones_from_patch_omegas(
        omega_by_patch_rad_s=omega_by_patch,
        roll_deg=roll_deg,
        pitch_deg=pitch_deg,
        yaw_deg=yaw_deg,
        origin_m=origin_m,
    )


def build_legacy_box_mrf_zones_from_patch_omegas(
    *,
    omega_by_patch_rad_s: Mapping[str, float],
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
    origin_m: Vector3 = (0.0, 0.0, 0.0),
) -> list[MRFZoneSpec]:
    """Build transformed legacy-box MRF zones from explicit signed patch omegas."""

    required_patches = {patch_name for _, _, _, patch_name, _, _ in _LEGACY_BOX_ROTORS}
    missing = sorted(required_patches - set(omega_by_patch_rad_s))
    if missing:
        raise ValueError(f"Missing MRF omega values for patches: {', '.join(missing)}")

    zones = [
        MRFZoneSpec(
            name=name,
            cell_zone=cell_zone,
            cylinder_name=cylinder_name,
            source_patch=patch_name,
            centre_m=centre,
            axis=LEGACY_BOX_BASE_AXIS,
            radius_m=LEGACY_BOX_MRF_RADIUS_M,
            height_m=LEGACY_BOX_MRF_HEIGHT_M,
            omega_rad_s=float(omega_by_patch_rad_s[patch_name]),
            notes=[
                "Legacy BoxQuadcopterCase MRF reference.",
                "Legacy CAD pose is treated as the zero-attitude setpoint.",
            ],
        )
        for name, cell_zone, cylinder_name, patch_name, centre, direction in _LEGACY_BOX_ROTORS
    ]

    transform = rotation_matrix(roll_deg=roll_deg, pitch_deg=pitch_deg, yaw_deg=yaw_deg)
    return [transform_mrf_zone(zone, transform, origin_m) for zone in zones]


def build_legacy_box_rotor_disk_sources(
    *,
    omega_rad_s: float,
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
    origin_m: Vector3 = (0.0, 0.0, 0.0),
) -> list[RotorDiskSourceSpec]:
    """Build transformed OpenFOAM rotorDisk sources for the legacy quadcopter."""

    omega_by_patch = {
        source_patch: sign * omega_rad_s
        for _, _, _, source_patch, _, sign in _LEGACY_BOX_ROTORS
    }
    return build_legacy_box_rotor_disk_sources_from_patch_omegas(
        omega_by_patch_rad_s=omega_by_patch,
        roll_deg=roll_deg,
        pitch_deg=pitch_deg,
        yaw_deg=yaw_deg,
        origin_m=origin_m,
    )


def build_legacy_box_rotor_disk_sources_from_patch_omegas(
    *,
    omega_by_patch_rad_s: dict[str, float],
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
    origin_m: Vector3 = (0.0, 0.0, 0.0),
) -> list[RotorDiskSourceSpec]:
    """Build rotorDisk sources from explicit signed propeller angular speeds."""

    missing = [
        source_patch
        for _, _, _, source_patch, _, _ in _LEGACY_BOX_ROTORS
        if source_patch not in omega_by_patch_rad_s
    ]
    if missing:
        raise ValueError(f"Missing rotor-disk omega values for patches: {', '.join(missing)}")

    base_axis = normalise_vector(LEGACY_BOX_BASE_AXIS)
    # The source axis is the intended downstream jet direction. For this legacy
    # zero pose, propellers are expected to push flow downwards, opposite the
    # geometric blade normal.
    disk_axis = (-base_axis[0], -base_axis[1], -base_axis[2])
    sources = [
        RotorDiskSourceSpec(
            name=f"{name}RotorDisk",
            cell_zone=cell_zone,
            centre_m=centre,
            axis=disk_axis,
            radius_m=LEGACY_BOX_MRF_RADIUS_M,
            height_m=LEGACY_BOX_MRF_HEIGHT_M,
            omega_rad_s=omega_by_patch_rad_s[source_patch],
            source_patch=source_patch,
            notes=[
                "OpenFOAM rotorDisk fvOption source term.",
                "This is an actuator-style momentum source, not a resolved moving blade.",
            ],
        )
        for name, cell_zone, _, source_patch, centre, _ in _LEGACY_BOX_ROTORS
    ]

    transform = rotation_matrix(roll_deg=roll_deg, pitch_deg=pitch_deg, yaw_deg=yaw_deg)
    return [transform_rotor_disk_source(source, transform, origin_m) for source in sources]
