from __future__ import annotations

from pathlib import Path

from whittle.evals.planning import run_planning_evals_from_file


def test_planning_eval_fixtures_pass() -> None:
    result = run_planning_evals_from_file(Path("examples/planning_eval_cases.json"))

    assert result.passed
    assert result.case_count >= 6
    assert result.failed_count == 0
