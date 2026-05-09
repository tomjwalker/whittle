# Current Plan

## Objective

Stabilize Whittle V0.1: a deterministic, typed OpenFOAM case writer for drone
external aerodynamics, with short-run controls and recorded OpenFOAM shakedown
findings.

## Status

- State: V0 complete; V0.1 cleanup complete
- Owner: Tom / Codex
- Last updated: 2026-05-09

## Acceptance Criteria

- Legacy split drone surfaces are copied into `assets/legacy_box_quadcopter`.
- `uv run whittle write-case --preset legacy-box --output outputs/legacy_box_v0`
  writes an inspectable OpenFOAM case.
- `uv run pytest` passes.
- Generated reports include warnings, assumptions, files written, and visible
  trace events.
- CLI supports short smoke runs through `--max-iterations` and
  `--write-interval`.

## Workstreams

1. Persist project context and V0 plan. Done.
2. Implement typed models, STL metadata, geometry presets, and case writing.
   Done.
3. Add tests and CLI smoke path. Done.
4. Record first WSL/OpenFOAM run findings and tune small generator issues.

## Risks And Blockers

- The local hexacopter STL is large and may require future splitting or
  decimation before meshing.
- OpenFOAM execution is available in WSL but is not yet automated from Whittle.
- First `legacy-box` mesh completed but `checkMesh` failed one quality check:
  17 highly skew faces, max skewness about 8.43. This is acceptable for V0
  smoke but not a validated CFD-quality mesh.

## Next Steps

1. Add a V1 deterministic planning/eval harness around natural-language
   scenario requests.
2. Later decide whether to add a WSL copy/run helper that writes logs to an
   ignored run directory.

## Validation

- Unit tests cover metadata, presets, generated patches, required files, and
  reports.
- CLI smoke command writes a complete case without running OpenFOAM.
- Manual OpenFOAM shakedown in WSL completed `blockMesh`, `snappyHexMesh`,
  `checkMesh`, and started `simpleFoam` on the generated legacy case.
