from __future__ import annotations

import asyncio

from whittle.agents.cfd_planning_agent import run_planning_agent


def test_agent_plan_deterministic_fallback_ready_for_review() -> None:
    response = asyncio.run(
        run_planning_agent(
            "Set up cruise at 5 m/s with spinning propellers.",
            case_name="agent_test",
            deterministic=True,
        )
    )

    assert response.source == "deterministic_fallback"
    assert response.status == "ready_for_human_review"
    assert response.scenario_plan is not None
    assert response.scenario_plan.spec is not None
    assert response.scenario_plan.spec.rotor_model == "mrf"


def test_agent_plan_deterministic_fallback_clarifies_vague_request() -> None:
    response = asyncio.run(
        run_planning_agent(
            "Make it more aerodynamic.",
            case_name="agent_vague",
            deterministic=True,
        )
    )

    assert response.status == "needs_clarification"
    assert response.scenario_plan is not None
    assert response.scenario_plan.spec is None
    assert response.next_actions
