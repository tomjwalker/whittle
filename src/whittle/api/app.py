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
    run_planning_agent,
    stream_planning_agent,
)
from whittle.models.agent import PlanningAgentResponse
from whittle.models.case_spec import SimulationCaseSpec
from whittle.models.reports import CaseSetupReport, TraceEvent
from whittle.openfoam.case_writer import write_openfoam_case
from whittle.tools.physics_envelope import DEFAULT_PHYSICS_ENVELOPE


class PlanRequest(BaseModel):
    """Request body for planning a CFD case."""

    message: str
    case_name: str = "agent_planned_case"
    model: str | None = None
    thinking: str | bool | None = None
    deterministic: bool = False


class WriteCaseRequest(BaseModel):
    """Request body for writing files from a reviewed spec."""

    spec: SimulationCaseSpec
    output_root: str = "outputs/agent_cases"


class ApiHealth(BaseModel):
    """Health payload for local UI checks."""

    ok: bool = True
    app: str = "whittle"
    default_model: str = DEFAULT_AGENT_MODEL
    default_thinking: str = DEFAULT_AGENT_THINKING
    has_openai_api_key: bool = Field(default_factory=lambda: bool(os.getenv("OPENAI_API_KEY")))


def create_app() -> FastAPI:
    """Create the FastAPI app used by local development and the Next.js UI."""

    app = FastAPI(title="Whittle CFD Planning API", version="0.1.0")
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

    return app


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _case_output_dir(output_root: str, case_name: str) -> Path:
    root = Path(output_root)
    if root.is_absolute():
        return root / case_name
    return Path.cwd() / root / case_name


app = create_app()
