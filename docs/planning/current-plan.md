# Current Plan

## Objective

Build Whittle V0: a deterministic, typed OpenFOAM case writer for drone external
aerodynamics.

## Status

- State: in progress
- Owner: Tom / Codex
- Last updated: 2026-05-09

## Acceptance Criteria

- Legacy split drone surfaces are copied into `assets/legacy_box_quadcopter`.
- `uv run whittle write-case --preset legacy-box --output outputs/legacy_box_v0`
  writes an inspectable OpenFOAM case.
- `uv run pytest` passes.
- Generated reports include warnings, assumptions, files written, and visible
  trace events.

## Workstreams

1. Persist project context and V0 plan.
2. Implement typed models, STL metadata, geometry presets, and case writing.
3. Add tests and CLI smoke path.

## Risks And Blockers

- The local hexacopter STL is large and may require future splitting or
  decimation before meshing.
- OpenFOAM execution is available in WSL but is not part of V0 automation.

## Next Steps

1. Finish V0 package skeleton.
2. Generate and inspect `outputs/legacy_box_v0`.
3. Decide whether to add a WSL copy/run helper next.

## Validation

- Unit tests cover metadata, presets, generated patches, required files, and
  reports.
- CLI smoke command writes a complete case without running OpenFOAM.
