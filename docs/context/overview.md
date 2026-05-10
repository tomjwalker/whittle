# Whittle Overview

_Last updated: 2026-05-10_

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
- Current phase: V0.2 deterministic MRF and attitude-transform foundation,
  plus V1/V2 planning-agent scaffold
- Primary workflow: generate an inspectable OpenFOAM case skeleton for external
  drone aerodynamics from typed Pydantic models

## Architecture Snapshot

| Layer | Planned tech | Notes |
| --- | --- | --- |
| Core package | Python 3.11+, Pydantic v2 | Typed domain state and validation |
| Case writing | pathlib + deterministic templates | OpenFOAM file-generation first |
| Geometry | STL metadata reader, NumPy transforms | Current hex STL remains local/ignored |
| Planning layer | Deterministic heuristics first | `plan-request` rehearses the agent contract |
| Agent layer | PydanticAI | First planning agent scaffold added |
| Evals | pytest first, Pydantic Evals later | Start simple and deterministic |
| UI | Next.js | Local chat/spec console scaffold added |
| Solver | OpenFOAM v2012 in WSL | Execution is later than V0 case writing |
| Post-pro | ParaView 5.13.2 | Existing Windows install found |

For the current Pydantic model map, see `docs/context/schema-guide.md`.
For the supported CFD scenario envelope, see `docs/context/physics-envelope.md`.

## Constraints

- Keep the architecture small and legible.
- Use typed schemas as contracts between request, tools, generated files, and
  evals.
- Do not commit raw secrets or large local CAD directories.
- Keep the demo civil/educational: no weapons, targeting, evasion, or mission
  optimisation.
- Do not use FreeCAD preprocessing, actuator disk source terms, automated solver
  execution, or UI in the deterministic foundation.

## Non-Goals

- Perfect CFD automation.
- Fully converged CFD as a dependency for the first pass.
- Multi-agent orchestration before one typed orchestrator is useful.
- A polished frontend before CLI, tests, and evals are credible.

## Near-Term Priorities

1. Smoke-test the combined-attitude MRF case in WSL.
2. Exercise the new deterministic evals and PydanticAI agent with real API
   credentials.
3. Use the local Next.js UI to iterate on the scenario-honing workflow.
4. Decide whether the next physics step is differential rotor speeds or solver
   log parsing.

## Open Questions

- Whether the monolithic hexacopter STL needs decimation or splitting before it
  can mesh reliably.
- How robust the legacy MRF cell-zone generation is under additional
  roll/pitch/yaw transforms.

## Update Rule

Keep this page short enough for a new coding agent to absorb in a couple of
minutes.
