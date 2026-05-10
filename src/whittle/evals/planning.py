"""Small deterministic eval harness for scenario planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from whittle.tools.scenario_planner import plan_case_request


class PlanningEvalCase(BaseModel):
    """One planner fixture with expected high-level behavior."""

    name: str
    request: str
    expected_scenario_type: str
    expect_spec: bool
    expected_rotor_model: str | None = None
    expected_missing_contains: list[str] = Field(default_factory=list)
    expected_warning_contains: list[str] = Field(default_factory=list)


class PlanningEvalResult(BaseModel):
    """Result of evaluating one planner fixture."""

    name: str
    passed: bool
    failures: list[str] = Field(default_factory=list)
    observed: dict[str, Any] = Field(default_factory=dict)


class PlanningEvalSuiteResult(BaseModel):
    """Aggregate result for a deterministic planner eval run."""

    passed: bool
    case_count: int
    failed_count: int
    results: list[PlanningEvalResult]


def load_planning_eval_cases(path: Path) -> list[PlanningEvalCase]:
    """Load planner fixtures from a JSON file."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    return [PlanningEvalCase.model_validate(item) for item in raw]


def run_planning_evals(cases: list[PlanningEvalCase]) -> PlanningEvalSuiteResult:
    """Run deterministic planner fixtures and return machine-readable results."""

    results = [_run_case(case) for case in cases]
    failed_count = sum(1 for result in results if not result.passed)
    return PlanningEvalSuiteResult(
        passed=failed_count == 0,
        case_count=len(results),
        failed_count=failed_count,
        results=results,
    )


def run_planning_evals_from_file(path: Path) -> PlanningEvalSuiteResult:
    """Load and run deterministic planner fixtures from disk."""

    return run_planning_evals(load_planning_eval_cases(path))


def _run_case(case: PlanningEvalCase) -> PlanningEvalResult:
    plan = plan_case_request(case.request, case_name=case.name)
    failures: list[str] = []

    if plan.scenario_type != case.expected_scenario_type:
        failures.append(
            f"expected scenario_type {case.expected_scenario_type!r}, got {plan.scenario_type!r}"
        )
    if bool(plan.spec) != case.expect_spec:
        failures.append(f"expected spec presence {case.expect_spec}, got {bool(plan.spec)}")
    if case.expected_rotor_model and (
        not plan.spec or plan.spec.rotor_model != case.expected_rotor_model
    ):
        observed = plan.spec.rotor_model if plan.spec else None
        failures.append(f"expected rotor_model {case.expected_rotor_model!r}, got {observed!r}")

    missing_text = "\n".join(plan.missing_information).lower()
    for expected in case.expected_missing_contains:
        if expected.lower() not in missing_text:
            failures.append(f"missing_information did not contain {expected!r}")

    warning_text = "\n".join(plan.warnings).lower()
    for expected in case.expected_warning_contains:
        if expected.lower() not in warning_text:
            failures.append(f"warnings did not contain {expected!r}")

    return PlanningEvalResult(
        name=case.name,
        passed=not failures,
        failures=failures,
        observed={
            "scenario_type": plan.scenario_type,
            "has_spec": bool(plan.spec),
            "rotor_model": plan.spec.rotor_model if plan.spec else None,
            "missing_information": plan.missing_information,
            "warnings": plan.warnings,
        },
    )
