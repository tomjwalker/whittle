"""Command-line interface for Whittle V0."""

from __future__ import annotations

import argparse
from pathlib import Path

from whittle.openfoam.case_writer import write_openfoam_case
from whittle.tools.attitude_suite import write_attitude_smoke_suite
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_legacy_box_geometry, build_single_stl_geometry
from whittle.tools.scenario_planner import plan_case_request


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "write-case":
        report = _write_case(args)
        print(report.model_dump_json(indent=2))
        return 0 if report.can_run else 1
    if args.command == "write-attitude-suite":
        reports = _write_attitude_suite(args)
        print("[" + ",\n".join(report.model_dump_json(indent=2) for report in reports) + "]")
        return 0 if all(report.can_run for report in reports) else 1
    if args.command == "plan-request":
        plan = plan_case_request(args.request, case_name=args.case_name)
        print(plan.model_dump_json(indent=2))
        return 0 if not plan.missing_information else 1

    parser.print_help()
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="whittle",
        description="Typed OpenFOAM case setup tools for the Whittle CFD agent demo.",
    )
    subparsers = parser.add_subparsers(dest="command")

    write_case = subparsers.add_parser("write-case", help="Write a deterministic OpenFOAM case.")
    write_case.add_argument(
        "--preset",
        choices=["legacy-box"],
        help="Use a built-in geometry preset.",
    )
    write_case.add_argument("--geometry", type=Path, help="Path to a local STL geometry file.")
    write_case.add_argument(
        "--geometry-mode",
        choices=["single-stl"],
        default="single-stl",
        help="Geometry interpretation when --geometry is supplied.",
    )
    write_case.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output OpenFOAM case directory.",
    )
    write_case.add_argument("--velocity", type=float, help="Reference inlet velocity in m/s.")
    write_case.add_argument(
        "--rotor-model",
        choices=["none", "mrf", "actuator-disk-placeholder"],
        default="none",
        help="Rotor modelling option. MRF is currently supported for --preset legacy-box.",
    )
    write_case.add_argument(
        "--mrf-omega-rad-s",
        type=float,
        default=1000.0,
        help="Unsigned rotor MRF angular speed in rad/s; signs alternate by rotor.",
    )
    write_case.add_argument("--roll-deg", type=float, default=0.0, help="Additional roll angle.")
    write_case.add_argument("--pitch-deg", type=float, default=0.0, help="Additional pitch angle.")
    write_case.add_argument("--yaw-deg", type=float, default=0.0, help="Additional yaw angle.")
    write_case.add_argument(
        "--transform-origin",
        type=float,
        nargs=3,
        metavar=("X", "Y", "Z"),
        default=(0.0, 0.0, 0.0),
        help="Rigid transform origin in metres.",
    )
    write_case.add_argument(
        "--max-iterations",
        type=int,
        default=500,
        help="simpleFoam endTime iteration count. Use a small value for smoke runs.",
    )
    write_case.add_argument(
        "--write-interval",
        type=int,
        default=100,
        help="OpenFOAM writeInterval in solver iterations.",
    )
    write_case.add_argument(
        "--case-name",
        help="OpenFOAM case name. Defaults to output directory name.",
    )

    attitude_suite = subparsers.add_parser(
        "write-attitude-suite",
        help="Write B/C MRF attitude smoke cases under one output root.",
    )
    attitude_suite.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs"),
        help="Directory under which B/C smoke case directories are written.",
    )
    attitude_suite.add_argument("--velocity", type=float, default=5.0)
    attitude_suite.add_argument("--mrf-omega-rad-s", type=float, default=1000.0)
    attitude_suite.add_argument("--max-iterations", type=int, default=5)
    attitude_suite.add_argument("--write-interval", type=int, default=5)

    plan_request = subparsers.add_parser(
        "plan-request",
        help="Deterministically plan a rough natural-language CFD request.",
    )
    plan_request.add_argument("request", help="Natural-language CFD setup request.")
    plan_request.add_argument("--case-name", default="planned_case")
    return parser


def _write_case(args: argparse.Namespace):
    case_name = args.case_name or args.output.name
    if args.max_iterations <= 0:
        raise SystemExit("--max-iterations must be greater than zero.")
    if args.write_interval <= 0:
        raise SystemExit("--write-interval must be greater than zero.")
    if args.mrf_omega_rad_s <= 0:
        raise SystemExit("--mrf-omega-rad-s must be greater than zero.")

    if args.preset == "legacy-box":
        geometry = build_legacy_box_geometry()
        velocity = args.velocity if args.velocity is not None else 5.0
    elif args.geometry:
        geometry = build_single_stl_geometry(args.geometry)
        velocity = args.velocity if args.velocity is not None else 10.0
    else:
        raise SystemExit("write-case requires either --preset legacy-box or --geometry PATH.")

    rotor_model = (
        "actuator_disk_placeholder"
        if args.rotor_model == "actuator-disk-placeholder"
        else args.rotor_model
    )

    spec = build_case_spec(
        case_name=case_name,
        geometry=geometry,
        velocity_mps=velocity,
        max_iterations=args.max_iterations,
        write_interval=args.write_interval,
        rotor_model=rotor_model,
        mrf_omega_rad_s=args.mrf_omega_rad_s,
        roll_deg=args.roll_deg,
        pitch_deg=args.pitch_deg,
        yaw_deg=args.yaw_deg,
        transform_origin_m=tuple(args.transform_origin),
    )
    return write_openfoam_case(spec, args.output)


def _write_attitude_suite(args: argparse.Namespace):
    if args.max_iterations <= 0:
        raise SystemExit("--max-iterations must be greater than zero.")
    if args.write_interval <= 0:
        raise SystemExit("--write-interval must be greater than zero.")
    if args.velocity <= 0:
        raise SystemExit("--velocity must be greater than zero.")
    if args.mrf_omega_rad_s <= 0:
        raise SystemExit("--mrf-omega-rad-s must be greater than zero.")

    return write_attitude_smoke_suite(
        args.output_root,
        velocity_mps=args.velocity,
        mrf_omega_rad_s=args.mrf_omega_rad_s,
        max_iterations=args.max_iterations,
        write_interval=args.write_interval,
    )


if __name__ == "__main__":
    raise SystemExit(main())
