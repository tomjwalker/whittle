"""WSL/OpenFOAM command helpers for reviewed local cases."""

from __future__ import annotations

import asyncio
import shlex
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OpenFOAMRunConfig:
    """Local WSL run settings for a generated OpenFOAM case."""

    case_dir: Path
    case_name: str
    distro: str = "Ubuntu-22.04"
    bashrc: str = "/opt/OpenFOAM/OpenFOAM-v2012/etc/bashrc"


def build_wsl_openfoam_script(config: OpenFOAMRunConfig) -> str:
    """Build a non-destructive WSL script that copies and runs a generated case."""

    case_dir = config.case_dir.resolve()
    commands = ["blockMesh", "snappyHexMesh -overwrite"]
    if (case_dir / "system" / "topoSetDict").exists():
        commands.append("topoSet")
    commands.extend(["checkMesh", "simpleFoam"])

    command_block = "\n".join(_openfoam_step(command) for command in commands)
    return (
        "set -euo pipefail\n"
        f"source {shlex.quote(config.bashrc)}\n"
        f"SRC=$(wslpath -a {shlex.quote(str(case_dir))})\n"
        f"CASE_NAME={shlex.quote(config.case_name)}\n"
        'BASE="$HOME/OpenFOAM/cases/$CASE_NAME"\n'
        'TARGET="$BASE"\n'
        "N=1\n"
        'while [ -e "$TARGET" ]; do TARGET="${BASE}_run${N}"; N=$((N + 1)); done\n'
        'mkdir -p "$TARGET"\n'
        'cp -a "$SRC/." "$TARGET/"\n'
        'cd "$TARGET"\n'
        'mkdir -p run_logs\n'
        "run_whittle_step()\n"
        "{\n"
        '    local command="$1"\n'
        '    local slug="$2"\n'
        '    echo "__WHITTLE_STEP_START__ ${command}"\n'
        "    set +e\n"
        '    bash -lc "${command}" 2>&1 | tee "run_logs/${slug}.log"\n'
        "    local status=${PIPESTATUS[0]}\n"
        "    set -e\n"
        '    echo "__WHITTLE_STEP_DONE__ ${command} status=${status}"\n'
        '    if [ "${status}" -ne 0 ] && [ "${slug}" != "checkMesh" ]; then\n'
        "        exit ${status}\n"
        "    fi\n"
        "}\n"
        'echo "__WHITTLE_TARGET__ $TARGET"\n'
        f"{command_block}\n"
        'echo "__WHITTLE_DONE__ $TARGET"\n'
    )


async def stream_wsl_openfoam_run(config: OpenFOAMRunConfig) -> AsyncIterator[dict[str, str]]:
    """Run OpenFOAM in WSL and stream structured output events."""

    script = build_wsl_openfoam_script(config)
    yield {"type": "run_start", "message": f"Starting OpenFOAM run for {config.case_name}."}

    process = await asyncio.create_subprocess_exec(
        "wsl",
        "-d",
        config.distro,
        "bash",
        "-lc",
        script,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert process.stdout is not None
    async for raw_line in process.stdout:
        line = raw_line.decode("utf-8", errors="replace").rstrip()
        yield _event_for_line(line)

    return_code = await process.wait()
    status = "run_complete" if return_code == 0 else "run_failed"
    yield {"type": status, "message": f"OpenFOAM exited with code {return_code}."}


def _openfoam_step(command: str) -> str:
    slug = command.split()[0]
    return f"run_whittle_step {shlex.quote(command)} {shlex.quote(slug)}"


def _event_for_line(line: str) -> dict[str, str]:
    if line.startswith("__WHITTLE_TARGET__ "):
        return {"type": "target", "message": line.removeprefix("__WHITTLE_TARGET__ ")}
    if line.startswith("__WHITTLE_DONE__ "):
        return {"type": "done", "message": line.removeprefix("__WHITTLE_DONE__ ")}
    if line.startswith("__WHITTLE_STEP_START__ "):
        return {"type": "step_start", "message": line.removeprefix("__WHITTLE_STEP_START__ ")}
    if line.startswith("__WHITTLE_STEP_DONE__ "):
        return {"type": "step_done", "message": line.removeprefix("__WHITTLE_STEP_DONE__ ")}
    return {"type": "line", "message": line}
