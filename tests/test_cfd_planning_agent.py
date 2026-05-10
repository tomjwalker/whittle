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


def test_agent_plan_deterministic_fallback_rejects_spin_in_place() -> None:
    response = asyncio.run(
        run_planning_agent(
            "I'd like to simulate my drone spinning in place.",
            case_name="agent_spin",
            deterministic=True,
        )
    )

    assert response.status == "out_of_scope"
    assert response.scenario_plan is not None
    assert response.scenario_plan.scenario_type == "hover_or_takeoff"
    assert response.scenario_plan.spec is None


def test_agent_plan_deterministic_fallback_rejects_yawing_in_place() -> None:
    response = asyncio.run(
        run_planning_agent(
            "I want to simulate my drone yawing in place.",
            case_name="agent_yaw_in_place",
            deterministic=True,
        )
    )

    assert response.status == "out_of_scope"
    assert response.scenario_plan is not None
    assert response.scenario_plan.scenario_type == "hover_or_takeoff"
    assert response.scenario_plan.spec is None
    assert any("yaw rate" in action for action in response.next_actions)


def test_agent_plan_deterministic_fallback_handles_trim_question() -> None:
    response = asyncio.run(
        run_planning_agent(
            "At 10 m/s, what kind of pitch and rotor speeds would support that drone speed?",
            case_name="agent_trim",
            deterministic=True,
        )
    )

    assert response.status == "needs_clarification"
    assert response.scenario_plan is not None
    assert response.scenario_plan.scenario_type == "trim_guidance"
    assert response.scenario_plan.spec is None
    assert any("sweep" in action for action in response.next_actions)
