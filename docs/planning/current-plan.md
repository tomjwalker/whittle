# Current Plan

## Objective

Build Whittle V0.2: deterministic MRF rotor-zone generation and rigid
roll/pitch/yaw attitude transforms for the legacy quadcopter case.

## Status

- State: V0/V0.1 complete; V0.2 B/C1 smoke checks passed; V1 deterministic
  evals and V2 planning-agent scaffold started
- Owner: Tom / Codex
- Last updated: 2026-05-10

## Acceptance Criteria

- Legacy split drone surfaces are copied into `assets/legacy_box_quadcopter`.
- `uv run whittle write-case --preset legacy-box --output outputs/legacy_box_v0`
  writes an inspectable OpenFOAM case.
- `uv run pytest` passes.
- Generated reports include warnings, assumptions, files written, and visible
  trace events.
- CLI supports short smoke runs through `--max-iterations` and
  `--write-interval`.
- CLI supports `--rotor-model mrf`, `--mrf-omega-rad-s`, `--roll-deg`,
  `--pitch-deg`, `--yaw-deg`, and `--transform-origin`.
- Generated MRF cases include `constant/MRFProperties`, `system/topoSetDict`,
  and matching rotor `cellZone` names.
- CLI can write the B/C attitude smoke-case suite.
- CLI can deterministically plan a rough natural-language request into a
  `ScenarioPlan` and optional `SimulationCaseSpec`.
- CLI can run deterministic planning eval fixtures.
- CLI can run a PydanticAI planning agent with deterministic fallback when no
  API key is configured.
- FastAPI exposes local planning and write-case endpoints.
- Next.js local UI can stream visible trace events and inspect the typed spec.

## Workstreams

1. Persist project context and V0 plan. Done.
2. Implement typed models, STL metadata, geometry presets, and case writing.
   Done.
3. Add tests and CLI smoke path. Done.
4. Record first WSL/OpenFOAM run findings and tune small generator issues. Done.
5. Add typed MRF zones and attitude transforms. Done for file generation.
6. Add machine-checkable physics envelope and deterministic scenario planner.
   First pass done.
7. Add deterministic eval harness, PydanticAI planning agent, FastAPI endpoint,
   and local Next.js UI. First pass done.

## Risks And Blockers

- The local hexacopter STL is large and may require future splitting or
  decimation before meshing.
- OpenFOAM execution is available in WSL but is not yet automated from Whittle.
- First `legacy-box` mesh completed but `checkMesh` failed one quality check:
  17 highly skew faces, max skewness about 8.43. This is acceptable for V0
  smoke but not a validated CFD-quality mesh.
- First MRF smoke run meshed successfully enough for V0.2 but failed at
  `simpleFoam` because `topoSet` had not been generated/run, leaving zero
  `cellZones`. The generator now writes `system/topoSetDict` and MRF `Allrun`
  executes `topoSet` after `snappyHexMesh`.
- Pitch-transformed MRF smoke case passed the current C1 acceptance test:
  `topoSet` generated nonzero transformed `prop*Zone` cell zones, `checkMesh`
  reported those zones, and `simpleFoam` created all four MRF zones and reached
  `Time = 5`.

## Next Steps

1. Smoke-test `legacy_box_mrf_combined_smoke` in OpenFOAM. If it passes, treat
   roll/yaw individual cases as optional debugging cases rather than mandatory
   Sunday blockers.
2. Run the deterministic eval harness after every planner/schema change.
3. Add an OpenAI API key locally and smoke-test `whittle agent-plan` without
   deterministic fallback.
4. Start the FastAPI + Next.js UI and iterate on the interview-style planning
   loop.

## Validation

- Unit tests cover metadata, presets, generated patches, required files, and
  reports.
- CLI smoke command writes a complete case without running OpenFOAM.
- Manual OpenFOAM shakedown in WSL completed `blockMesh`, `snappyHexMesh`,
  `checkMesh`, and started `simpleFoam` on the generated legacy case.
- Unit tests cover MRF zone generation, transform signs, unit-length rotor
  axes, STL transformation, and generated MRF OpenFOAM files.
- MRF case generation now tests that `system/topoSetDict` is written and that
  `Allrun` calls `topoSet` before `simpleFoam`.
- `uv run whittle write-attitude-suite --output-root outputs` generated B,
  C1 pitch, C2 roll, C3 yaw, and C4 combined attitude smoke cases.
- Manual OpenFOAM pitch smoke completed `blockMesh`, `snappyHexMesh`,
  `topoSet`, `checkMesh`, and five `simpleFoam` iterations.
- Unit tests cover physics-envelope validation and deterministic scenario
  planning.
- Unit tests cover deterministic eval fixtures, deterministic agent fallback,
  and FastAPI planning endpoints.
