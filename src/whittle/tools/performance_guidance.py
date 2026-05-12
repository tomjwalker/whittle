"""Heuristic performance and rotor-command guidance for CFD scenario planning."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field


class RotorSpeedGuidance(BaseModel):
    """Signed MRF omega values for the legacy-box propeller patches."""

    propeller_fl_rad_s: float
    propeller_fr_rad_s: float
    propeller_bl_rad_s: float
    propeller_br_rad_s: float
    convention: str = (
        "Signs match the legacy MRF setup: front-right and back-left positive, "
        "front-left and back-right negative."
    )


class PerformanceGuidance(BaseModel):
    """Small transparent lookup/interpolation result for planning, not trim proof."""

    mode: Literal["baseline_cruise", "yaw_manoeuvre_proxy"]
    velocity_mps: float
    recommended_pitch_deg: float
    baseline_omega_rad_s: float
    baseline_rotor_speeds_rad_s: RotorSpeedGuidance
    pitch_sweep_deg: list[float] = Field(default_factory=list)
    omega_sweep_rad_s: list[float] = Field(default_factory=list)
    yaw_rate_deg_s: float | None = None
    yaw_proxy_rotor_speeds_rad_s: RotorSpeedGuidance | None = None
    confidence: Literal["heuristic"] = "heuristic"
    method: str
    limitations: list[str] = Field(default_factory=list)


class MotionIntent(BaseModel):
    """Soft manoeuvre request before it crosses into an OpenFOAM case contract."""

    u_mps: float = 0.0
    v_mps: float = 0.0
    w_mps: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float | None = None
    yaw_deg: float = 0.0
    roll_rate_deg_s: float = 0.0
    pitch_rate_deg_s: float = 0.0
    yaw_rate_deg_s: float = 0.0


class MotionRotorCommand(BaseModel):
    """Heuristic mapping from a motion intent to signed per-rotor MRF speeds."""

    motion: MotionIntent
    reference_speed_mps: float
    inferred_pitch_deg: float
    base_omega_rad_s: float
    roll_delta_rad_s: float
    pitch_delta_rad_s: float
    yaw_delta_rad_s: float
    rotor_speeds_rad_s: RotorSpeedGuidance
    is_rolling: bool
    is_pitching: bool
    is_yawing: bool
    confidence: Literal["heuristic"] = "heuristic"
    method: str
    limitations: list[str] = Field(default_factory=list)


_CRUISE_TABLE = [
    {
        "velocity_mps": 0.0,
        "pitch_deg": 0.0,
        "omega_rad_s": 1000.0,
        "pitch_sweep_deg": [0.0, 3.0, 6.0],
        "omega_sweep_rad_s": [800.0, 1000.0, 1200.0],
    },
    {
        "velocity_mps": 5.0,
        "pitch_deg": 0.0,
        "omega_rad_s": 1000.0,
        "pitch_sweep_deg": [0.0, 3.0, 6.0],
        "omega_sweep_rad_s": [800.0, 1000.0, 1200.0],
    },
    {
        "velocity_mps": 10.0,
        "pitch_deg": 6.0,
        "omega_rad_s": 1100.0,
        "pitch_sweep_deg": [3.0, 6.0, 9.0, 12.0],
        "omega_sweep_rad_s": [900.0, 1100.0, 1300.0],
    },
    {
        "velocity_mps": 15.0,
        "pitch_deg": 10.0,
        "omega_rad_s": 1400.0,
        "pitch_sweep_deg": [6.0, 10.0, 14.0, 18.0],
        "omega_sweep_rad_s": [1100.0, 1400.0, 1700.0],
    },
    {
        "velocity_mps": 20.0,
        "pitch_deg": 14.0,
        "omega_rad_s": 1700.0,
        "pitch_sweep_deg": [8.0, 12.0, 16.0, 20.0],
        "omega_sweep_rad_s": [1300.0, 1700.0, 2100.0],
    },
]

_RATE_EPS = 1e-9
_YAW_RATE_REF_DEG_S = 90.0
_ROLL_RATE_REF_DEG_S = 90.0
_PITCH_RATE_REF_DEG_S = 90.0
_YAW_DELTA_FRACTION_AT_REF = 0.12
_ROLL_DELTA_FRACTION_AT_REF = 0.10
_PITCH_DELTA_FRACTION_AT_REF = 0.10
_MAX_DELTA_FRACTION = 0.25


def get_cruise_performance_guidance(
    velocity_mps: float,
    *,
    yaw_rate_deg_s: float | None = None,
) -> PerformanceGuidance:
    """Return an explicit heuristic for baseline pitch and signed rotor speeds.

    This is deliberately a small lookup plus linear interpolation. It is useful
    for expert-led UX defaults and interview demos, but it is not a flight
    dynamics trim solver or a CFD-calibrated surrogate.
    """

    clamped_velocity = _clamp(
        velocity_mps,
        _CRUISE_TABLE[0]["velocity_mps"],
        _CRUISE_TABLE[-1]["velocity_mps"],
    )
    low, high = _bracket(clamped_velocity)
    pitch = _interp(clamped_velocity, low, high, "pitch_deg")
    omega = _interp(clamped_velocity, low, high, "omega_rad_s")
    nearest = min(_CRUISE_TABLE, key=lambda item: abs(item["velocity_mps"] - clamped_velocity))
    baseline = _symmetric_rotor_speeds(omega)
    yaw_proxy = None
    mode: Literal["baseline_cruise", "yaw_manoeuvre_proxy"] = "baseline_cruise"
    if yaw_rate_deg_s is not None:
        mode = "yaw_manoeuvre_proxy"
        yaw_proxy = _yaw_proxy_rotor_speeds(omega, yaw_rate_deg_s)

    limitations = [
        "Values are heuristic defaults for case planning, not solved aircraft trim.",
        "Use force and moment outputs from CFD runs to evaluate whether the point is balanced.",
        "The current steady simpleFoam writer cannot impose yaw_dot directly.",
    ]
    if velocity_mps != clamped_velocity:
        limitations.append(
            f"Requested velocity was clamped to the table range {clamped_velocity:g} m/s."
        )

    return PerformanceGuidance(
        mode=mode,
        velocity_mps=velocity_mps,
        recommended_pitch_deg=round(pitch, 3),
        baseline_omega_rad_s=round(omega, 3),
        baseline_rotor_speeds_rad_s=baseline,
        pitch_sweep_deg=[float(value) for value in nearest["pitch_sweep_deg"]],
        omega_sweep_rad_s=[float(value) for value in nearest["omega_sweep_rad_s"]],
        yaw_rate_deg_s=yaw_rate_deg_s,
        yaw_proxy_rotor_speeds_rad_s=yaw_proxy,
        method=(
            "Transparent MVP table with linear interpolation between cruise-speed "
            "anchors; replace with CFD/flight-data calibration when data exists."
        ),
        limitations=limitations,
    )


def get_motion_rotor_command(
    *,
    u_mps: float = 0.0,
    v_mps: float = 0.0,
    w_mps: float = 0.0,
    roll_deg: float = 0.0,
    pitch_deg: float | None = None,
    yaw_deg: float = 0.0,
    roll_rate_deg_s: float = 0.0,
    pitch_rate_deg_s: float = 0.0,
    yaw_rate_deg_s: float = 0.0,
) -> MotionRotorCommand:
    """Map a lay manoeuvre intent to a bounded per-rotor MRF speed proposal.

    This is the MVP performance model: a transparent cruise-speed lookup plus
    additive differential rotor-speed deltas for roll, pitch, and yaw rates. It
    is intentionally simple and auditable until there is CFD or flight data to
    fit a calibrated surrogate.
    """

    reference_speed = math.sqrt(u_mps**2 + v_mps**2 + w_mps**2)
    guidance = get_cruise_performance_guidance(reference_speed)
    base_omega = guidance.baseline_omega_rad_s
    inferred_pitch = guidance.recommended_pitch_deg if pitch_deg is None else pitch_deg

    roll_delta = _rate_delta(
        roll_rate_deg_s,
        base_omega,
        _ROLL_RATE_REF_DEG_S,
        _ROLL_DELTA_FRACTION_AT_REF,
    )
    pitch_delta = _rate_delta(
        pitch_rate_deg_s,
        base_omega,
        _PITCH_RATE_REF_DEG_S,
        _PITCH_DELTA_FRACTION_AT_REF,
    )
    yaw_delta = _rate_delta(
        yaw_rate_deg_s,
        base_omega,
        _YAW_RATE_REF_DEG_S,
        _YAW_DELTA_FRACTION_AT_REF,
    )

    rotor_speeds = RotorSpeedGuidance(
        propeller_fl_rad_s=round(-(base_omega + pitch_delta - roll_delta - yaw_delta), 3),
        propeller_fr_rad_s=round(base_omega + pitch_delta + roll_delta + yaw_delta, 3),
        propeller_bl_rad_s=round(base_omega - pitch_delta - roll_delta + yaw_delta, 3),
        propeller_br_rad_s=round(-(base_omega - pitch_delta + roll_delta - yaw_delta), 3),
        convention=(
            "Signs match the legacy MRF setup. Differential terms are additive: "
            "yaw changes opposite torque pairs, roll changes left/right thrust, "
            "and pitch changes front/back thrust."
        ),
    )

    limitations = [
        "This is a heuristic control proxy, not a solved dynamics trim controller.",
        (
            "roll_dot, pitch_dot, and yaw_dot are not imposed as body angular "
            "velocities in simpleFoam."
        ),
        "The rates are converted into a steady differential-MRF rotor-speed proposal.",
        (
            "Vehicle mass, inertia, motor constants, and blade-resolved thrust "
            "coefficients are not modelled."
        ),
        "Use CFD forces and moments to refine the table once simulation data exists.",
    ]
    if reference_speed > _CRUISE_TABLE[-1]["velocity_mps"]:
        limitations.append(
            f"Reference speed {reference_speed:g} m/s exceeds the table; "
            "baseline omega was clamped."
        )

    return MotionRotorCommand(
        motion=MotionIntent(
            u_mps=u_mps,
            v_mps=v_mps,
            w_mps=w_mps,
            roll_deg=roll_deg,
            pitch_deg=pitch_deg,
            yaw_deg=yaw_deg,
            roll_rate_deg_s=roll_rate_deg_s,
            pitch_rate_deg_s=pitch_rate_deg_s,
            yaw_rate_deg_s=yaw_rate_deg_s,
        ),
        reference_speed_mps=round(reference_speed, 3),
        inferred_pitch_deg=round(inferred_pitch, 3),
        base_omega_rad_s=round(base_omega, 3),
        roll_delta_rad_s=round(roll_delta, 3),
        pitch_delta_rad_s=round(pitch_delta, 3),
        yaw_delta_rad_s=round(yaw_delta, 3),
        rotor_speeds_rad_s=rotor_speeds,
        is_rolling=abs(roll_rate_deg_s) > _RATE_EPS,
        is_pitching=abs(pitch_rate_deg_s) > _RATE_EPS,
        is_yawing=abs(yaw_rate_deg_s) > _RATE_EPS,
        method=(
            "Transparent MVP table/interpolation for baseline cruise omega, "
            "with bounded additive roll/pitch/yaw-rate differentials. Replace "
            "with calibrated CFD/flight-data interpolation when data exists."
        ),
        limitations=limitations,
    )


def rotor_speed_guidance_to_patch_omega_map(
    rotor_speeds: RotorSpeedGuidance,
) -> dict[str, float]:
    """Convert frontend-friendly FL/FR/BL/BR names to legacy OpenFOAM patch names."""

    return {
        "propeller_fl": rotor_speeds.propeller_fl_rad_s,
        "propeller_fr": rotor_speeds.propeller_fr_rad_s,
        "propeller_bl": rotor_speeds.propeller_bl_rad_s,
        "propeller_br": rotor_speeds.propeller_br_rad_s,
    }


def _symmetric_rotor_speeds(omega: float) -> RotorSpeedGuidance:
    return RotorSpeedGuidance(
        propeller_fl_rad_s=round(-omega, 3),
        propeller_fr_rad_s=round(omega, 3),
        propeller_bl_rad_s=round(omega, 3),
        propeller_br_rad_s=round(-omega, 3),
    )


def _yaw_proxy_rotor_speeds(omega: float, yaw_rate_deg_s: float) -> RotorSpeedGuidance:
    if abs(yaw_rate_deg_s) <= _RATE_EPS:
        return _symmetric_rotor_speeds(omega)
    direction = 1.0 if yaw_rate_deg_s >= 0 else -1.0
    delta = _clamp(abs(yaw_rate_deg_s) / 90.0 * omega * 0.12, 50.0, omega * 0.25)
    return RotorSpeedGuidance(
        propeller_fl_rad_s=round(-(omega - direction * delta), 3),
        propeller_fr_rad_s=round(omega + direction * delta, 3),
        propeller_bl_rad_s=round(omega + direction * delta, 3),
        propeller_br_rad_s=round(-(omega - direction * delta), 3),
    )


def _rate_delta(
    rate_deg_s: float,
    base_omega: float,
    reference_rate_deg_s: float,
    fraction_at_reference_rate: float,
) -> float:
    raw = rate_deg_s / reference_rate_deg_s * base_omega * fraction_at_reference_rate
    limit = base_omega * _MAX_DELTA_FRACTION
    return _clamp(raw, -limit, limit)


def _bracket(velocity_mps: float) -> tuple[dict[str, object], dict[str, object]]:
    for low, high in zip(_CRUISE_TABLE, _CRUISE_TABLE[1:], strict=False):
        if low["velocity_mps"] <= velocity_mps <= high["velocity_mps"]:
            return low, high
    return _CRUISE_TABLE[-1], _CRUISE_TABLE[-1]


def _interp(
    velocity_mps: float,
    low: dict[str, object],
    high: dict[str, object],
    key: Literal["pitch_deg", "omega_rad_s"],
) -> float:
    low_v = float(low["velocity_mps"])
    high_v = float(high["velocity_mps"])
    if high_v == low_v:
        return float(low[key])
    t = (velocity_mps - low_v) / (high_v - low_v)
    return float(low[key]) + t * (float(high[key]) - float(low[key]))


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)
