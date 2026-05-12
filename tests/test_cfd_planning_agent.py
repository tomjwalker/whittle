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


def test_agent_plan_deterministic_fallback_accepts_spin_in_place_proxy() -> None:
    response = asyncio.run(
        run_planning_agent(
            "I'd like to simulate my drone spinning in place.",
            case_name="agent_spin",
            deterministic=True,
        )
    )

    assert response.status == "ready_for_human_review"
    assert response.scenario_plan is not None
    assert response.scenario_plan.scenario_type == "motion_proxy"
    assert response.scenario_plan.spec is not None
    assert response.scenario_plan.spec.flow_regime == "steady_incompressible_motion_proxy_mrf"


def test_agent_plan_deterministic_fallback_accepts_yawing_in_place_proxy() -> None:
    response = asyncio.run(
        run_planning_agent(
            "I want to simulate my drone yawing in place.",
            case_name="agent_yaw_in_place",
            deterministic=True,
        )
    )

    assert response.status == "ready_for_human_review"
    assert response.scenario_plan is not None
    assert response.scenario_plan.scenario_type == "motion_proxy"
    assert response.scenario_plan.spec is not None
    assert len(response.next_actions) <= 2
    assert any("differential-MRF" in action for action in response.next_actions)
    assert any(event.event_type == "MotionRotorCommandRun" for event in response.trace_events)


def test_agent_plan_deterministic_fallback_accepts_static_hover_smoke() -> None:
    response = asyncio.run(
        run_planning_agent(
            "I'd like to simulate hover-in-place with no floor and rotors at 1000 rad/s.",
            case_name="agent_static_hover",
            deterministic=True,
        )
    )

    assert response.status == "ready_for_human_review"
    assert response.phase == "human_review"
    assert response.scenario_plan is not None
    assert response.scenario_plan.scenario_type == "static_hover_mrf"
    assert response.scenario_plan.spec is not None
    assert response.scenario_plan.spec.reference_velocity_mps == 0.0
    assert response.scenario_plan.spec.rotor_model == "mrf"
    assert "smoke approximation" in response.assistant_message


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
    assert "expert-default baseline" in response.assistant_message
    assert any("sweep" in action for action in response.next_actions)
    assert len(response.next_actions) <= 2
    assert any(event.event_type == "PerformanceGuidanceRun" for event in response.trace_events)


def test_agent_deterministic_fallback_uses_previous_plan_for_follow_up() -> None:
    first = asyncio.run(
        run_planning_agent(
            "Set up cruise at 5 m/s with spinning propellers.",
            case_name="agent_memory",
            deterministic=True,
        )
    )

    response = asyncio.run(
        run_planning_agent(
            "Make it faster at 10 m/s.",
            case_name="agent_memory",
            deterministic=True,
            previous_plan=first.scenario_plan,
        )
    )

    assert response.scenario_plan is not None
    assert response.scenario_plan.spec is not None
    assert response.scenario_plan.spec.reference_velocity_mps == 10.0
    assert response.scenario_plan.spec.rotor_model == "mrf"
    assert any(
        event.event_type == "PreviousPlanApplied" for event in response.scenario_plan.trace_events
    )
