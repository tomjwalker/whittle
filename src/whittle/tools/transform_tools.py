"""Rigid-body transform helpers for geometry and rotor zones."""

from __future__ import annotations

import math

import numpy as np

from whittle.models.geometry import Vector3
from whittle.models.rotors import MRFZoneSpec, RotorDiskSourceSpec


def rotation_matrix(
    *,
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
) -> np.ndarray:
    """Build a right-handed body attitude matrix.

    Convention: x forward, y right, z up. Positive roll raises the right side,
    positive pitch raises the nose, and positive yaw rotates x toward y.
    """

    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)

    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)

    rx = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cr, -sr],
            [0.0, sr, cr],
        ]
    )
    ry_nose_up = np.array(
        [
            [cp, 0.0, -sp],
            [0.0, 1.0, 0.0],
            [sp, 0.0, cp],
        ]
    )
    rz = np.array(
        [
            [cy, -sy, 0.0],
            [sy, cy, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    return rz @ ry_nose_up @ rx


def has_nonzero_attitude(
    *,
    roll_deg: float = 0.0,
    pitch_deg: float = 0.0,
    yaw_deg: float = 0.0,
    tolerance: float = 1e-12,
) -> bool:
    return any(abs(value) > tolerance for value in (roll_deg, pitch_deg, yaw_deg))


def transform_point(
    point: Vector3,
    matrix: np.ndarray,
    origin: Vector3 = (0.0, 0.0, 0.0),
) -> Vector3:
    vector = np.array(point, dtype=float)
    origin_vector = np.array(origin, dtype=float)
    output = matrix @ (vector - origin_vector) + origin_vector
    return _to_vector3(output)


def transform_vector(vector: Vector3, matrix: np.ndarray) -> Vector3:
    output = matrix @ np.array(vector, dtype=float)
    return _to_vector3(output)


def normalise_vector(vector: Vector3) -> Vector3:
    values = np.array(vector, dtype=float)
    norm = np.linalg.norm(values)
    if norm == 0:
        return (0.0, 0.0, 0.0)
    return _to_vector3(values / norm)


def transform_mrf_zone(
    zone: MRFZoneSpec,
    matrix: np.ndarray,
    origin: Vector3 = (0.0, 0.0, 0.0),
) -> MRFZoneSpec:
    return zone.model_copy(
        update={
            "centre_m": transform_point(zone.centre_m, matrix, origin),
            "axis": normalise_vector(transform_vector(zone.axis, matrix)),
        }
    )


def transform_rotor_disk_source(
    source: RotorDiskSourceSpec,
    matrix: np.ndarray,
    origin: Vector3 = (0.0, 0.0, 0.0),
) -> RotorDiskSourceSpec:
    return source.model_copy(
        update={
            "centre_m": transform_point(source.centre_m, matrix, origin),
            "axis": normalise_vector(transform_vector(source.axis, matrix)),
            "ref_direction": normalise_vector(transform_vector(source.ref_direction, matrix)),
        }
    )


def mrf_cylinder_endpoints(zone: MRFZoneSpec) -> tuple[Vector3, Vector3]:
    return cylinder_endpoints(zone.centre_m, zone.axis, zone.height_m)


def rotor_disk_cylinder_endpoints(source: RotorDiskSourceSpec) -> tuple[Vector3, Vector3]:
    return cylinder_endpoints(source.centre_m, source.axis, source.height_m)


def cylinder_endpoints(
    centre_m: Vector3,
    axis: Vector3,
    height_m: float,
) -> tuple[Vector3, Vector3]:
    axis_values = np.array(normalise_vector(axis), dtype=float)
    centre = np.array(centre_m, dtype=float)
    half_height = 0.5 * height_m
    return (
        _to_vector3(centre - axis_values * half_height),
        _to_vector3(centre + axis_values * half_height),
    )


def _to_vector3(values: np.ndarray) -> Vector3:
    return (float(values[0]), float(values[1]), float(values[2]))
