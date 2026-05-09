# Whittle Overview

_Last updated: 2026-05-09_

## Product Vision

Whittle is a weekend autodidactic and interview-prep project for typed AI engineering
workflows around CFD case setup.

The project turns a messy natural-language drone CFD request into typed,
validated OpenFOAM case setup artefacts. It is deliberately not a claim to solve
CFD automation in a weekend. The point is the production-shaped workflow:

messy expert request -> structured state -> deterministic tools / agents ->
validation / evals -> human review -> product loop.

## Scope Right Now

- Primary user: Tom, as an AI engineer with CFD/F1 aerodynamics background
- Current phase: V0 deterministic foundation
- Primary workflow: generate an inspectable OpenFOAM case skeleton for external
  drone aerodynamics from typed Pydantic models

## Architecture Snapshot

| Layer | Planned tech | Notes |
| --- | --- | --- |
| Core package | Python 3.11+, Pydantic v2 | Typed domain state and validation |
| Case writing | pathlib + deterministic templates | OpenFOAM file-generation first |
| Geometry | STL metadata reader, NumPy later | Current hex STL remains local/ignored |
| Agent layer | PydanticAI | Added after deterministic tools work |
| Evals | pytest first, Pydantic Evals later | Start simple and deterministic |
| UI | Streamlit optional | Only after CLI/core/evals work |
| Solver | OpenFOAM v2012 in WSL | Execution is later than V0 case writing |
| Post-pro | ParaView 5.13.2 | Existing Windows install found |

## Constraints

- Keep the architecture small and legible.
- Use typed schemas as contracts between request, tools, generated files, and
  evals.
- Do not commit raw secrets or large local CAD directories.
- Keep the demo civil/educational: no weapons, targeting, evasion, or mission
  optimisation.
- Do not use FreeCAD preprocessing, MRF, actuator disk source terms, solver
  execution, or UI in V0.

## Non-Goals

- Perfect CFD automation.
- Fully converged CFD as a dependency for the first pass.
- Multi-agent orchestration before one typed orchestrator is useful.
- A polished frontend before CLI, tests, and evals are credible.

## Near-Term Priorities

1. Generate a deterministic OpenFOAM case from typed models.
2. Preserve legacy Isembard/OpenFOAM geometry assets that are useful for a
   first rerun.
3. Add tests and smoke commands that make the workflow explainable in
   interviews.

## Open Questions

- Whether the monolithic hexacopter STL needs decimation or splitting before it
  can mesh reliably.
- Which OpenFOAM execution command should be automated first once file
  generation is stable.

## Update Rule

Keep this page short enough for a new coding agent to absorb in a couple of
minutes.
