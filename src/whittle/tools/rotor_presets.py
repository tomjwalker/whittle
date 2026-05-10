"""Rotor presets for known legacy geometries."""

from __future__ import annotations

from whittle.models.geometry import Vector3
from whittle.models.rotors import MRFZoneSpec
from whittle.tools.transform_tools import normalise_vector, rotation_matrix, transform_mrf_zone

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
            omega_rad_s=direction * omega_rad_s,
            notes=[
                "Legacy BoxQuadcopterCase MRF reference.",
                "Legacy CAD pose is treated as the zero-attitude setpoint.",
            ],
        )
        for name, cell_zone, cylinder_name, patch_name, centre, direction in _LEGACY_BOX_ROTORS
    ]

    transform = rotation_matrix(roll_deg=roll_deg, pitch_deg=pitch_deg, yaw_deg=yaw_deg)
    return [transform_mrf_zone(zone, transform, origin_m) for zone in zones]
