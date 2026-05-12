"""Machine-checkable physics envelope for early Whittle cases."""

from __future__ import annotations

from whittle.models.case_spec import SimulationCaseSpec
from whittle.models.planning import PhysicsEnvelope

DEFAULT_PHYSICS_ENVELOPE = PhysicsEnvelope(
    notes=[
        "Educational steady incompressible low-speed drone external-aero envelope.",
        "Limits are guardrails for planning and evals, not validated aircraft performance data.",
    ]
)


def validate_physics_envelope(
    spec: SimulationCaseSpec,
    envelope: PhysicsEnvelope = DEFAULT_PHYSICS_ENVELOPE,
) -> tuple[list[str], list[str], list[str]]:
    """Return checks, warnings, and missing info against the early demo envelope."""

    checks: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    velocity = spec.reference_velocity_mps
    if velocity < 0:
        missing.append("reference_velocity_mps must not be negative.")
    elif velocity == 0 and _is_zero_freestream_rotor_proxy(spec):
        checks.append("Zero freestream is allowed for static/differential rotor proxy cases.")
        warnings.append(
            "Zero-freestream MRF proxy or rotor-disk proxy flow is an educational "
            "steady approximation, not a validated hover trim, takeoff, yaw-rate, "
            "or ground-effect simulation."
        )
    elif velocity < envelope.min_reference_velocity_mps:
        missing.append(
            "reference_velocity_mps is below the early-envelope minimum "
            f"of {envelope.min_reference_velocity_mps:g} m/s."
        )
    elif velocity > envelope.hard_max_reference_velocity_mps:
        missing.append(
            "reference_velocity_mps exceeds the early-envelope hard limit "
            f"of {envelope.hard_max_reference_velocity_mps:g} m/s."
        )
    elif velocity > envelope.typical_max_reference_velocity_mps:
        warnings.append(
            "reference_velocity_mps is above the typical small-quadcopter cruise "
            f"range of {envelope.typical_max_reference_velocity_mps:g} m/s."
        )
    else:
        checks.append("Reference velocity is inside the early physics envelope.")

    for label, angle in (
        ("roll_angle_deg", spec.roll_angle_deg),
        ("pitch_angle_deg", spec.pitch_angle_deg),
        ("yaw_angle_deg", spec.yaw_angle_deg),
    ):
        if abs(angle) > envelope.max_attitude_angle_deg:
            missing.append(
                f"{label} exceeds the early-envelope limit of "
                f"{envelope.max_attitude_angle_deg:g} degrees."
            )
    if not any(abs(value) > envelope.max_attitude_angle_deg for value in _attitude(spec)):
        checks.append("Attitude angles are inside the early physics envelope.")

    if spec.rotor_model == "mrf":
        max_omega = max((abs(zone.omega_rad_s) for zone in spec.mrf_zones), default=0.0)
        if max_omega > envelope.hard_max_mrf_omega_rad_s:
            missing.append(
                "MRF omega exceeds the early-envelope hard limit "
                f"of {envelope.hard_max_mrf_omega_rad_s:g} rad/s."
            )
        else:
            checks.append("MRF omega is inside the early physics envelope.")
    elif spec.rotor_model == "rotor_disk":
        max_omega = max(
            (abs(source.omega_rad_s) for source in spec.rotor_disk_sources),
            default=0.0,
        )
        if max_omega > envelope.hard_max_mrf_omega_rad_s:
            missing.append(
                "Rotor-disk omega exceeds the early-envelope hard limit "
                f"of {envelope.hard_max_mrf_omega_rad_s:g} rad/s."
            )
        else:
            checks.append("Rotor-disk omega is inside the early physics envelope.")

    return checks, warnings, missing


def _attitude(spec: SimulationCaseSpec) -> tuple[float, float, float]:
    return spec.roll_angle_deg, spec.pitch_angle_deg, spec.yaw_angle_deg


def _is_zero_freestream_rotor_proxy(spec: SimulationCaseSpec) -> bool:
    return (
        spec.flow_regime
        in {
            "steady_incompressible_static_mrf_hover",
            "steady_incompressible_motion_proxy_mrf",
            "steady_incompressible_static_rotor_disk_hover",
            "steady_incompressible_motion_proxy_rotor_disk",
        }
        and spec.rotor_model in {"mrf", "rotor_disk"}
    )
