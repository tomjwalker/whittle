# V0 OpenFOAM Case Writer Plan

_Last updated: 2026-05-09_

## Goal

Create the deterministic foundation for Whittle before adding PydanticAI:
typed case state in, OpenFOAM case files and a reviewable setup report out.

## Inputs

- Preferred first-run asset: split legacy Isembard/OpenFOAM surfaces from
  `BoxQuadcopterCase`.
- Real target asset: local ignored `cad/drone_model_hex.stl`.

The legacy split surfaces are smaller, already patch-separated, and known from
last year's OpenFOAM workflow. The hexacopter STL remains the actual target
geometry, but may need a future mesh-prep pass.

## V0 Command Targets

```bash
uv run whittle write-case --preset legacy-box --output outputs/legacy_box_v0
uv run whittle write-case --geometry cad/drone_model_hex.stl --geometry-mode single-stl --output outputs/hex_v0 --velocity 10
```

## Generated Case

Required directories:

```text
0/
constant/
constant/triSurface/
system/
```

Required files:

```text
0/U
0/p
0/k
0/omega
0/nut
constant/transportProperties
constant/turbulenceProperties
system/controlDict
system/blockMeshDict
system/snappyHexMeshDict
system/fvSchemes
system/fvSolution
Allrun
Allclean
<case>.foam
case_report.json
```

## Deliberate Exclusions

- No FreeCAD subprocess.
- No MRF or actuator disk source terms.
- No OpenFOAM solver execution.
- No Streamlit UI.
- No PydanticAI orchestration until deterministic tools and tests exist.

## Trace Events

The report should use visible trace events such as:

- `RequestReceived`
- `GeometryResolved`
- `CaseSpecBuilt`
- `AssumptionsRecorded`
- `OpenFOAMFilesPlanned`
- `FilesWritten`
- `ValidationRun`
- `HumanReviewNeeded`

These are engineering trace events, not hidden model reasoning.
