from __future__ import annotations

from whittle.agents.prompt_loader import load_cfd_planning_prompts


def test_cfd_planning_prompt_loads_from_prompt_file() -> None:
    prompts = load_cfd_planning_prompts()

    assert "layperson" in prompts.system_prompt
    assert "get_performance_guidance" in prompts.runtime_prompt
    assert "get_motion_rotor_command" in prompts.runtime_prompt
