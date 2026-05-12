# Current Plan

## Objective

Build Whittle V0.2: deterministic MRF rotor-zone generation and rigid
roll/pitch/yaw attitude transforms for the legacy quadcopter case.

## Status

- State: V0/V0.1 complete; V0.2 B/C smoke checks passed; V1/V2
  interview-agent scaffold now has intent, typed memory, UI timeline, optional
  Logfire wiring, and a first rotor-disk source-term fidelity step
- Owner: Tom / Codex
- Last updated: 2026-05-11

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
- Planning-agent responses separate conversation phase, coaching, suggested
  replies, and writeable typed specs.
- Planner supports a clearly caveated static hover MRF smoke case at
  zero freestream, while keeping floor/takeoff/ground-effect requests blocked.
- Planner emits a `ScenarioIntent` before the hard `SimulationCaseSpec`.
- FastAPI/UI requests can pass the previous structured plan for follow-up
  refinements.
- UI shows intent state and visible action chips without exposing hidden
  chain-of-thought.
- Optional Logfire instrumentation is documented and env-gated.
- Planning agent prompt is stored outside Python code and instructs expert-led,
  layperson-friendly, max-two-choice coaching.
- A deterministic performance-guidance table/tool suggests baseline pitch,
  signed MRF rotor speeds, and future sweep values without claiming solved trim.
- A deterministic motion-command tool maps `u/v/w`, attitude, and
  `roll_dot/pitch_dot/yaw_dot` to bounded per-rotor MRF speeds for caveated
  bespoke manoeuvre proxy cases.
- CLI supports `--rotor-model rotor-disk` and writes `system/fvOptions`
  `rotorDisk` source terms for stronger downwash smoke tests.
- FastAPI/Next.js expose a human-triggered WSL OpenFOAM run stream for reviewed
  cases.

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
- OpenFOAM execution is available in WSL and now has a minimal fixed-command
  runner. It is intentionally HITL and local-only, not a general terminal.
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

1. Use `docs/planning/interview-sprint-plan.md` as the Monday-to-Wednesday
   priority guide.
2. Add more eval fixtures for lay-user multi-turn conversations and confirm the
   new expert-led prompt reduces turns.
3. Prepare the Anima and PhysicsX answer bank around this architecture.
4. Run the deterministic eval harness after every planner/schema change.
5. Inspect the rotor-disk hover case for downwash sign/strength, then decide
   whether the next fidelity step is log parsing, stronger source calibration,
   AMI/sliding mesh, or better CAD.

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
- Unit tests cover `ScenarioIntent`, previous-plan follow-up memory, and API
  previous-plan requests.
- Frontend lint/build and Playwright UI smoke test pass for the action timeline
  and no-stale-spec behavior.
- Unit tests cover performance-guidance interpolation, motion-command rotor
  deltas, per-rotor MRF case writing, and prompt loading.
- Unit tests cover rotor-disk case writing and the WSL run-command builder.
- `outputs/legacy_box_rotor_disk_hover_t500` was generated for overnight
  OpenFOAM testing.
