"""Command-line interface for Whittle V0."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from whittle.agents.cfd_planning_agent import run_planning_agent
from whittle.evals.planning import run_planning_evals_from_file
from whittle.openfoam.case_writer import write_openfoam_case
from whittle.openfoam.wsl_runner import OpenFOAMRunConfig, stream_wsl_openfoam_run
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
    if args.command == "agent-plan":
        response = asyncio.run(_agent_plan(args))
        print(response.model_dump_json(indent=2))
        return 0 if response.status not in {"error", "out_of_scope"} else 1
    if args.command == "eval-planner":
        result = run_planning_evals_from_file(args.cases)
        print(result.model_dump_json(indent=2))
        return 0 if result.passed else 1
    if args.command == "run-openfoam":
        return asyncio.run(_run_openfoam(args))

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
        choices=["none", "mrf", "rotor-disk", "actuator-disk-placeholder"],
        default="none",
        help=(
            "Rotor modelling option. MRF and rotor-disk are currently supported "
            "for --preset legacy-box."
        ),
    )
    write_case.add_argument(
        "--mrf-omega-rad-s",
        type=float,
        default=1000.0,
        help="Unsigned rotor angular speed in rad/s; signs alternate by rotor.",
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

    agent_plan = subparsers.add_parser(
        "agent-plan",
        help="Run the PydanticAI planning agent, with deterministic fallback if no API key is set.",
    )
    agent_plan.add_argument("request", help="Natural-language CFD setup request.")
    agent_plan.add_argument("--case-name", default="agent_planned_case")
    agent_plan.add_argument(
        "--model",
        default=None,
        help=(
            "PydanticAI model string. Defaults to WHITTLE_AGENT_MODEL or "
            "openai-responses:gpt-5.4-mini."
        ),
    )
    agent_plan.add_argument(
        "--thinking",
        default=None,
        help="Reasoning effort, e.g. low, medium, high, xhigh.",
    )
    agent_plan.add_argument(
        "--deterministic",
        action="store_true",
        help="Skip the model call and use deterministic planning.",
    )

    eval_planner = subparsers.add_parser(
        "eval-planner",
        help="Run deterministic planner fixtures.",
    )
    eval_planner.add_argument(
        "--cases",
        type=Path,
        default=Path("examples/planning_eval_cases.json"),
        help="JSON fixture file.",
    )

    run_openfoam = subparsers.add_parser(
        "run-openfoam",
        help="Copy a generated case into WSL and run the OpenFOAM command sequence.",
    )
    run_openfoam.add_argument("--case-dir", type=Path, required=True)
    run_openfoam.add_argument("--case-name", help="WSL target case name. Defaults to folder name.")
    run_openfoam.add_argument("--distro", default="Ubuntu-22.04")
    run_openfoam.add_argument(
        "--bashrc",
        default="/opt/OpenFOAM/OpenFOAM-v2012/etc/bashrc",
        help="OpenFOAM bashrc path inside WSL.",
    )
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

    rotor_model = {
        "actuator-disk-placeholder": "actuator_disk_placeholder",
        "rotor-disk": "rotor_disk",
    }.get(args.rotor_model, args.rotor_model)
    flow_regime = (
        "steady_incompressible_static_rotor_disk_hover"
        if rotor_model == "rotor_disk" and velocity == 0
        else "steady_incompressible_external"
    )

    spec = build_case_spec(
        case_name=case_name,
        geometry=geometry,
        velocity_mps=velocity,
        flow_regime=flow_regime,
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


async def _agent_plan(args: argparse.Namespace):
    return await run_planning_agent(
        args.request,
        case_name=args.case_name,
        model=args.model,
        thinking=args.thinking,
        deterministic=args.deterministic,
    )


async def _run_openfoam(args: argparse.Namespace) -> int:
    config = OpenFOAMRunConfig(
        case_dir=args.case_dir,
        case_name=args.case_name or args.case_dir.name,
        distro=args.distro,
        bashrc=args.bashrc,
    )
    exit_code = 1
    async for event in stream_wsl_openfoam_run(config):
        print(f"[{event['type']}] {event['message']}", flush=True)
        if event["type"] == "run_complete":
            exit_code = 0
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
