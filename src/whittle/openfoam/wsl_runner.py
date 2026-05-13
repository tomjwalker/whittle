"""WSL/OpenFOAM command helpers for reviewed local cases."""

from __future__ import annotations

import asyncio
import shlex
import subprocess
import threading
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
        "set -eo pipefail\n"
        f"source {shlex.quote(config.bashrc)}\n"
        "set -u\n"
        f"SRC=$(wslpath -a {shlex.quote(str(case_dir))})\n"
        f"WHITTLE_CASE_NAME={shlex.quote(config.case_name)}\n"
        'BASE="$HOME/OpenFOAM/cases/$WHITTLE_CASE_NAME"\n'
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

    queue: asyncio.Queue[dict[str, str] | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit(event: dict[str, str] | None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def run_process() -> None:
        try:
            process = subprocess.Popen(
                ["wsl", "-d", config.distro, "bash", "-s"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            assert process.stdin is not None
            process.stdin.write(script.encode("utf-8"))
            process.stdin.close()
            assert process.stdout is not None
            for raw_line in process.stdout:
                line = raw_line.decode("utf-8", errors="replace").rstrip()
                emit(_event_for_line(line))
            return_code = process.wait()
            status = "run_complete" if return_code == 0 else "run_failed"
            emit({"type": status, "message": f"OpenFOAM exited with code {return_code}."})
        except Exception as exc:
            emit(
                {
                    "type": "run_failed",
                    "message": (
                        "OpenFOAM runner failed before completion: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                }
            )
        finally:
            emit(None)

    thread = threading.Thread(
        target=run_process,
        name=f"whittle-openfoam-{config.case_name}",
        daemon=True,
    )
    thread.start()

    while True:
        event = await queue.get()
        if event is None:
            break
        yield event


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
