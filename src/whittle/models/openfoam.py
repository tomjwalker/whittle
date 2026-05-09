"""OpenFOAM file reporting models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class OpenFOAMCaseFiles(BaseModel):
    """OpenFOAM files planned and written for a generated case."""

    case_dir: Path
    system_files: list[str] = Field(default_factory=list)
    constant_files: list[str] = Field(default_factory=list)
    initial_condition_files: list[str] = Field(default_factory=list)
    files_written: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

