# Whittle

Whittle is a small typed AI-engineering demo for drone CFD case setup.

The deterministic foundation creates typed OpenFOAM case skeletons from
geometry inputs. A first PydanticAI planning layer and local Next.js UI now sit
above that foundation so vague requests can be turned into reviewed
`ScenarioPlan` and `SimulationCaseSpec` objects.

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

Generate a 5-iteration MRF rotor smoke case:

```bash
uv run whittle write-case --preset legacy-box --rotor-model mrf --mrf-omega-rad-s 1000 --max-iterations 5 --write-interval 5 --output outputs/legacy_box_mrf_smoke
```

Generate a 5-iteration pitch-transformed MRF case:

```bash
uv run whittle write-case --preset legacy-box --rotor-model mrf --mrf-omega-rad-s 1000 --pitch-deg 10 --max-iterations 5 --write-interval 5 --output outputs/legacy_box_mrf_pitch10_smoke
```

Generate all B/C attitude smoke cases:

```bash
uv run whittle write-attitude-suite --output-root outputs --velocity 5 --mrf-omega-rad-s 1000 --max-iterations 5 --write-interval 5
```

Plan a rough request into typed scenario state:

```bash
uv run whittle plan-request "Set up external cruise over a quadcopter at 10 m/s with spinning propellers."
```

Run deterministic planner evals:

```bash
uv run whittle eval-planner
```

Run the planning agent. If `OPENAI_API_KEY` is not set, this returns a
deterministic fallback response using the same public contract:

```bash
uv run whittle agent-plan "Set up cruise at 5 m/s with spinning propellers." --case-name agent_demo
```

Start the local API and UI:

```bash
uv run uvicorn whittle.api.app:app --reload --port 8000

cd frontend
npm install
npm run dev
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
    MRFProperties optional
    transportProperties
    turbulenceProperties
    triSurface/
      *.stl
  system/
    controlDict
    blockMeshDict
    snappyHexMeshDict
    topoSetDict optional for MRF
    fvSchemes
    fvSolution
  Allrun
  Allclean
  case.foam
  case_report.json
```

## Deliberate Current Limits

- No FreeCAD preprocessing.
- No actuator disk source terms.
- No OpenFOAM solver execution from the agent/UI.
- No automatic case writing without human review.
- No hover/takeoff/ground-effect setup yet.

See `docs/context/physics-envelope.md` for the supported scenario envelope.
