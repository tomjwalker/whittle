"""FastAPI app for the Whittle planning demo."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI
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
    has_openai_api_key: bool = Field(default_factory=lambda: bool(os.getenv("OPENAI_API_KEY")))
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
    async def physics_envelope() -> dict[str, Any]:
        return DEFAULT_PHYSICS_ENVELOPE.model_dump(mode="json")

    @app.post("/api/plan", response_model=PlanningAgentResponse)
    async def plan(request: PlanRequest) -> PlanningAgentResponse:
        return await run_planning_agent(
            request.message,
            case_name=request.case_name,
            model=request.model,
            thinking=request.thinking,
            deterministic=request.deterministic,
            conversation_history=request.conversation_history,
            previous_plan=request.previous_plan,
        )

    @app.post("/api/plan/stream")
    async def plan_stream(request: PlanRequest) -> StreamingResponse:
        async def iterator() -> AsyncIterator[bytes]:
            async for event in stream_planning_agent(
                request.message,
                case_name=request.case_name,
                model=request.model,
                thinking=request.thinking,
                deterministic=request.deterministic,
                conversation_history=request.conversation_history,
                previous_plan=request.previous_plan,
            ):
                yield (json.dumps(event) + "\n").encode("utf-8")

        return StreamingResponse(iterator(), media_type="application/x-ndjson")

    @app.post("/api/write-case", response_model=CaseSetupReport)
    async def write_case(request: WriteCaseRequest) -> CaseSetupReport:
        output_dir = _case_output_dir(request.output_root, request.spec.case_name)
        report = write_openfoam_case(request.spec, output_dir)
        report.trace_events.append(
            TraceEvent(
                event_type="FilesWrittenByApi",
                message="OpenFOAM case files were written from a reviewed agent spec.",
                data={"output_dir": str(output_dir)},
            )
        )
        return report

    @app.post("/api/openfoam/run/stream")
    async def openfoam_run_stream(request: RunOpenFOAMRequest) -> StreamingResponse:
        case_dir = _case_output_dir(request.output_root, request.case_name)
        config = OpenFOAMRunConfig(
            case_dir=case_dir,
            case_name=request.case_name,
            distro=request.distro,
            bashrc=request.bashrc,
        )

        async def iterator() -> AsyncIterator[bytes]:
            async for event in stream_wsl_openfoam_run(config):
                yield (json.dumps(event) + "\n").encode("utf-8")

        return StreamingResponse(iterator(), media_type="application/x-ndjson")

    return app


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = {item.strip() for item in raw.split(",") if item.strip()}
    origins.update({"http://localhost:3000", "http://127.0.0.1:3000"})
    return sorted(origins)


def _case_output_dir(output_root: str, case_name: str) -> Path:
    root = Path(output_root)
    if root.is_absolute():
        return root / case_name
    return Path.cwd() / root / case_name


app = create_app()
