# Whittle

Whittle is a small typed AI-engineering demo for drone CFD case setup.

The current V0 does not run CFD and does not call an LLM. It creates a typed,
deterministic OpenFOAM case skeleton from geometry inputs so the later
PydanticAI layer has reliable tools to orchestrate.

## Thesis

```text
messy expert request -> structured state -> tools / agents -> validation / evals -> human review -> product loop
```

For this project, the expert request is a drone OpenFOAM setup request. The
first artefact is a reviewable `CaseSetupReport` plus OpenFOAM case files.

## V0 Geometry Inputs

Whittle currently supports two geometry paths:

- `--preset legacy-box`: split body/propeller STLs copied from last year's
  local Isembard/OpenFOAM `BoxQuadcopterCase`.
- `--geometry ... --geometry-mode single-stl`: one local STL treated as a
  single no-slip drone wall patch.

The current monolithic hexacopter STL should stay under ignored `cad/` or
`CAD/`. It is supported as a local input but is not committed to the repo.

## Setup

```bash
uv sync --extra dev
```

## Commands

Generate the known-good legacy split-surface case:

```bash
uv run whittle write-case --preset legacy-box --output outputs/legacy_box_v0
```

Generate a case from the local ignored hexacopter STL:

```bash
uv run whittle write-case --geometry cad/drone_model_hex.stl --geometry-mode single-stl --output outputs/hex_v0 --velocity 10
```

Run checks:

```bash
uv run pytest
uv run ruff check
```

## Generated Case Shape

```text
case/
  0/
    U
    p
    k
    omega
    nut
  constant/
    transportProperties
    turbulenceProperties
    triSurface/
      *.stl
  system/
    controlDict
    blockMeshDict
    snappyHexMeshDict
    fvSchemes
    fvSolution
  Allrun
  Allclean
  case.foam
  case_report.json
```

## Deliberate V0 Limits

- No FreeCAD preprocessing.
- No MRF.
- No actuator disk source terms.
- No OpenFOAM solver execution.
- No Streamlit UI.
- No PydanticAI orchestration yet.

See `docs/planning/v0-openfoam-case-writer.md` for the implementation plan.
