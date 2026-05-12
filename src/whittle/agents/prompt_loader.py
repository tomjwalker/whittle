"""Load small agent prompt specs without adding a YAML dependency."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class AgentPrompts:
    """Prompt sections loaded from a repo-local YAML-like prompt file."""

    system_prompt: str
    runtime_prompt: str


PROMPT_DIR = Path(__file__).parent / "prompts"
CFD_PLANNING_PROMPT = PROMPT_DIR / "cfd_planning_agent.yaml"


@lru_cache(maxsize=1)
def load_cfd_planning_prompts() -> AgentPrompts:
    """Load the CFD planning agent prompts from a simple block-scalar file.

    The prompt file intentionally uses only top-level ``key: |`` blocks so we
    can keep prompts inspectable without introducing another runtime dependency.
    """

    text = CFD_PLANNING_PROMPT.read_text(encoding="utf-8")
    return AgentPrompts(
        system_prompt=_load_block_scalar(text, "system_prompt"),
        runtime_prompt=_load_block_scalar(text, "runtime_prompt"),
    )


def _load_block_scalar(text: str, key: str) -> str:
    marker = f"{key}: |"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != marker:
            continue
        block: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate and not candidate.startswith((" ", "\t")):
                break
            block.append(candidate[2:] if candidate.startswith("  ") else candidate)
        value = "\n".join(block).strip()
        if not value:
            raise ValueError(f"Prompt block `{key}` is empty in {CFD_PLANNING_PROMPT}.")
        return value
    raise ValueError(f"Prompt block `{key}` was not found in {CFD_PLANNING_PROMPT}.")
