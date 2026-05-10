# Brainstorm Backlog

Use this file for rough but reusable thinking.

## Problems Worth Solving

- `[Problem]`

## Product Ideas

- Add a WSL/OpenFOAM run helper after the case writer is stable. It should copy
  generated cases into `~/OpenFOAM/cases`, run explicit commands only after user
  confirmation, and write logs under an ignored case-local `run_logs/` directory.
- Build the front-of-workflow agent as a scenario-honing assistant: it asks the
  user whether the drone case is cruise, hover, climb, descent, gust response,
  or a simple geometry smoke test before generating a case spec.
- Build a small chat UI around `ScenarioPlan`: left side conversation, right
  side extracted fields, missing information, assumptions, physics-envelope
  checks, generated files, and visible trace events.
- Let the future PydanticAI agent mediate between layperson language and the
  deterministic planner/writer: ask clarifying questions, choose defaults from
  the physics envelope, and call typed tools only once the request is
  sufficiently specified.

## Hypotheses

- `[Hypothesis]`

## Research Questions

- How much of Pydantic Evals should V1 use immediately versus keeping a tiny
  custom harness first and adding Pydantic Evals as a parallel runner?
- Which `checkMesh` and `simpleFoam` log fields should become typed acceptance
  criteria for early educational runs?
- What are credible default cruise speeds, rotor speeds, and attitude limits
  for the legacy quadcopter geometry, and which should remain assumptions until
  backed by better data?

## Possible Experiments

- Parse a saved `checkMesh` log into a typed report: pass/fail count, max
  skewness, non-orthogonality, cell count, warning list, and recommended next
  action.
- Add a deterministic eval set for `plan-request`: cruise, missing speed,
  vague aerodynamic request, internal duct, hover/takeoff, pitch/yaw/roll, and
  out-of-envelope speed.

## Promotion Rule

If an idea becomes real work, move it into `current-plan.md` or a GitHub Issue.
