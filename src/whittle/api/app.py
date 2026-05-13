"""FastAPI app for the Whittle planning demo."""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from whittle.agents.cfd_planning_agent import (
    DEFAULT_AGENT_MODEL,
    DEFAULT_AGENT_THINKING,
    ConversationMessage,
    run_planning_agent,
    stream_planning_agent,
)
from whittle.models.agent import PlanningAgentResponse
from whittle.models.case_spec import SimulationCaseSpec
from whittle.models.planning import ScenarioPlan
from whittle.models.reports import CaseSetupReport, TraceEvent
from whittle.observability import configure_observability, logfire_enabled
from whittle.openfoam.case_writer import write_openfoam_case
from whittle.openfoam.wsl_runner import OpenFOAMRunConfig, stream_wsl_openfoam_run
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE


class PlanRequest(BaseModel):
    """Request body for planning a CFD case."""

    message: str
    case_name: str = "agent_planned_case"
    model: str | None = None
    thinking: str | bool | None = None
    deterministic: bool = False
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    previous_plan: ScenarioPlan | None = None


class WriteCaseRequest(BaseModel):
    """Request body for writing files from a reviewed spec."""

    spec: SimulationCaseSpec
    output_root: str = "outputs/agent_cases"


class RunOpenFOAMRequest(BaseModel):
    """Request body for HITL OpenFOAM execution in WSL."""

    case_name: str
    output_root: str = "outputs/agent_cases"
    distro: str = "Ubuntu-22.04"
    bashrc: str = "/opt/OpenFOAM/OpenFOAM-v2012/etc/bashrc"


class ApiHealth(BaseModel):
    """Health payload for local UI checks."""

    ok: bool = True
    app: str = "whittle"
    default_model: str = DEFAULT_AGENT_MODEL
    default_thinking: str = DEFAULT_AGENT_THINKING
    logfire_enabled: bool = Field(default_factory=logfire_enabled)


def create_app() -> FastAPI:
    """Create the FastAPI app used by local development and the Next.js UI."""

    app = FastAPI(title="Whittle CFD Planning API", version="0.1.0")
    configure_observability(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=ApiHealth)
    async def health() -> ApiHealth:
        return ApiHealth()

    @app.get("/api/physics-envelope")
    async def physics_envelope(request: Request) -> dict[str, Any]:
        _require_local_client(request)
        return DEFAULT_PHYSICS_ENVELOPE.model_dump(mode="json")

    @app.post("/api/plan", response_model=PlanningAgentResponse)
    async def plan(request: Request, body: PlanRequest) -> PlanningAgentResponse:
        _require_local_client(request)
        return await run_planning_agent(
            body.message,
            case_name=body.case_name,
            model=body.model,
            thinking=body.thinking,
            deterministic=body.deterministic,
            conversation_history=body.conversation_history,
            previous_plan=body.previous_plan,
        )

    @app.post("/api/plan/stream")
    async def plan_stream(request: Request, body: PlanRequest) -> StreamingResponse:
        _require_local_client(request)

        async def iterator() -> AsyncIterator[bytes]:
            async for event in stream_planning_agent(
                body.message,
                case_name=body.case_name,
                model=body.model,
                thinking=body.thinking,
                deterministic=body.deterministic,
                conversation_history=body.conversation_history,
                previous_plan=body.previous_plan,
            ):
                yield (json.dumps(event) + "\n").encode("utf-8")

        return StreamingResponse(iterator(), media_type="application/x-ndjson")

    @app.post("/api/write-case", response_model=CaseSetupReport)
    async def write_case(request: Request, body: WriteCaseRequest) -> CaseSetupReport:
        _require_local_client(request)
        output_dir = _case_output_dir(body.output_root, body.spec.case_name)
        report = write_openfoam_case(body.spec, output_dir)
        report.trace_events.append(
            TraceEvent(
                event_type="FilesWrittenByApi",
                message="OpenFOAM case files were written from a reviewed agent spec.",
                data={"output_dir": str(output_dir)},
            )
        )
        return report

    @app.post("/api/openfoam/run/stream")
    async def openfoam_run_stream(request: Request, body: RunOpenFOAMRequest) -> StreamingResponse:
        _require_local_client(request)
        case_dir = _case_output_dir(body.output_root, body.case_name)
        config = OpenFOAMRunConfig(
            case_dir=case_dir,
            case_name=body.case_name,
            distro=body.distro,
            bashrc=body.bashrc,
        )

        async def iterator() -> AsyncIterator[bytes]:
            try:
                async for event in stream_wsl_openfoam_run(config):
                    yield (json.dumps(event) + "\n").encode("utf-8")
            except Exception as exc:
                event = {
                    "type": "run_failed",
                    "message": (
                        "OpenFOAM runner failed before completion: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                }
                yield (json.dumps(event) + "\n").encode("utf-8")

        return StreamingResponse(iterator(), media_type="application/x-ndjson")

    return app


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = {item.strip() for item in raw.split(",") if item.strip()}
    origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
    return sorted(origins)


def _case_output_dir(output_root: str, case_name: str) -> Path:
    _validate_safe_path_fragment(output_root, "output_root")
    _validate_case_name(case_name)
    root = Path(output_root)
    if root.is_absolute():
        raise HTTPException(status_code=400, detail="output_root must be a relative path.")
    output_dir = (Path.cwd() / root / case_name).resolve()
    workspace = Path.cwd().resolve()
    if output_dir != workspace and workspace not in output_dir.parents:
        raise HTTPException(status_code=400, detail="Output path must stay inside the workspace.")
    return output_dir


def _validate_safe_path_fragment(value: str, field_name: str) -> None:
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a safe relative path.")


def _validate_case_name(case_name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", case_name):
        raise HTTPException(
            status_code=400,
            detail=(
                "case_name must be 1-80 characters and use only letters, numbers, "
                "dots, dashes, or underscores."
            ),
        )


def _require_local_client(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(
            status_code=403,
            detail=(
                "This local demo only allows API access from localhost."
            ),
        )


app = create_app()
