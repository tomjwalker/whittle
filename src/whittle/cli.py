"""Command-line interface for Whittle V0."""

from __future__ import annotations

import argparse
from pathlib import Path

from whittle.openfoam.case_writer import write_openfoam_case
from whittle.tools.case_tools import build_case_spec
from whittle.tools.geometry_presets import build_legacy_box_geometry, build_single_stl_geometry


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "write-case":
        report = _write_case(args)
        print(report.model_dump_json(indent=2))
        return 0 if report.can_run else 1

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
    return parser


def _write_case(args: argparse.Namespace):
    case_name = args.case_name or args.output.name
    if args.max_iterations <= 0:
        raise SystemExit("--max-iterations must be greater than zero.")
    if args.write_interval <= 0:
        raise SystemExit("--write-interval must be greater than zero.")

    if args.preset == "legacy-box":
        geometry = build_legacy_box_geometry()
        velocity = args.velocity if args.velocity is not None else 5.0
    elif args.geometry:
        geometry = build_single_stl_geometry(args.geometry)
        velocity = args.velocity if args.velocity is not None else 10.0
    else:
        raise SystemExit("write-case requires either --preset legacy-box or --geometry PATH.")

    spec = build_case_spec(
        case_name=case_name,
        geometry=geometry,
        velocity_mps=velocity,
        max_iterations=args.max_iterations,
        write_interval=args.write_interval,
    )
    return write_openfoam_case(spec, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
