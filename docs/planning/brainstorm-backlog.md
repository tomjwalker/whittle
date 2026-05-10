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
- Improve the first Next.js chat UI with saved conversations, richer trace
  timelines, and a diff view when the user revises a case spec.
- Let the planning agent accept multi-turn history and carry forward the
  previously reviewed `ScenarioPlan` instead of replanning from one prompt.

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
- Add Pydantic Evals alongside the custom JSON fixture harness once the
  deterministic cases stop changing daily.

## Promotion Rule

If an idea becomes real work, move it into `current-plan.md` or a GitHub Issue.
