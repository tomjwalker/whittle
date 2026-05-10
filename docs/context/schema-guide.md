# Schema Guide

_Last updated: 2026-05-09_

This project uses Pydantic models as explicit workflow state. The important
idea is that Whittle should not pass around anonymous dictionaries or hidden
LLM text. Each stage receives and returns typed objects that can be validated,
serialized, tested, evaluated, and shown to a human reviewer.

The current V0 schemas are intentionally small. They describe geometry,
simulation intent, OpenFOAM file output, and the human-reviewable report.

## Current Data Flow

```text
STL files
  -> StlMetadata
  -> GeometrySurfaceSpec
  -> DroneGeometrySpec
  -> BoundaryConditionPlan
  -> SimulationCaseSpec
  -> OpenFOAM case writer
  -> CaseSetupReport + TraceEvent list
```

In V1, the front of this chain will start from a natural-language request:

```text
messy user request
  -> planning/extraction layer
  -> SimulationCaseSpec
  -> validation/evals
  -> OpenFOAM case writer
```

## Geometry Schemas

Defined in `src/whittle/models/geometry.py`.

### `StlMetadata`

Small, read-only summary of an STL input.

```python
class StlMetadata(BaseModel):
    source_path: Path
    file_size_bytes: int
    format: Literal["binary", "ascii", "unknown"]
    triangle_count: int | None = None
    bounds_min: tuple[float, float, float] | None = None
    bounds_max: tuple[float, float, float] | None = None
    dimensions_raw: tuple[float, float, float] | None = None
    inferred_units: Literal["m", "mm", "unknown"] = "unknown"
    scale_to_m: float = 1.0
    warnings: list[str] = []
```

Purpose:

- Records what Whittle can infer from a CAD/STL file without running OpenFOAM.
- Helps detect large files, likely millimetre units, missing bounds, and other
  geometry risks early.
- Gives future evals deterministic facts to check, such as “large STL warning
  is present.”

### `GeometrySurfaceSpec`

One STL file mapped to one intended OpenFOAM patch.

```python
class GeometrySurfaceSpec(BaseModel):
    source_path: Path
    target_file_name: str
    patch_name: str
    role: Literal["body", "propeller", "drone", "unknown"]
    scale_to_m: float = 1.0
    metadata: StlMetadata | None = None
```

Purpose:

- Separates file identity from OpenFOAM patch identity.
- Lets split CAD surfaces become named patches such as `drone_body` and
  `propeller_fr`.
- Lets monolithic CAD become a single conservative patch, currently `drone`.

### `DroneGeometrySpec`

The full geometry bundle for one simulation case.

```python
class DroneGeometrySpec(BaseModel):
    name: str
    geometry_mode: Literal["single_stl", "surface_set"]
    surfaces: list[GeometrySurfaceSpec]
    units: Literal["m", "mm", "unknown"] = "unknown"
    scale_to_m: float = 1.0
    notes: list[str] = []
```

Purpose:

- Represents either the ignored local hexacopter STL or the legacy split
  BoxQuadcopter surfaces.
- Provides the patch list used by boundary-condition generation.
- Keeps geometry assumptions close to geometry facts.

## Case Schemas

Defined in `src/whittle/models/case_spec.py`.

### `BoundaryConditionPlan`

Patch-level OpenFOAM boundary intent.

```python
class BoundaryConditionPlan(BaseModel):
    inlet: str = "inlet"
    outlet: str = "outlet"
    farfield: list[str] = ["side1", "side2", "top", "bottom"]
    walls: list[str]
    reference_velocity_mps: float
    notes: list[str] = []
```

Purpose:

- Expresses the case boundary concept before writing OpenFOAM syntax.
- Makes patch consistency testable: every wall patch should appear in `0/U`,
  `0/p`, turbulence fields, and `snappyHexMeshDict`.

### `SimulationCaseSpec`

The central typed state object for the CFD setup.

```python
class SimulationCaseSpec(BaseModel):
    case_name: str
    geometry: DroneGeometrySpec
    boundary_conditions: BoundaryConditionPlan
    fluid: str = "air"
    flow_regime: str = "steady_incompressible_external"
    reference_velocity_mps: float
    angle_of_attack_deg: float = 0.0
    yaw_angle_deg: float = 0.0
    roll_angle_deg: float = 0.0
    pitch_angle_deg: float = 0.0
    rotor_model: Literal["none", "actuator_disk_placeholder"] = "none"
    solver_family: str = "simpleFoam"
    turbulence_model: str = "kOmegaSST"
    mesh_strategy: str = "blockMesh background mesh with snappyHexMesh surface snapping"
    kinematic_viscosity_m2_s: float = 1.5e-5
    air_density_kg_m3: float = 1.225
    max_iterations: int = 500
    write_interval: int = 100
    missing_information: list[str] = []
    assumptions: list[str] = []
    validation_checks: list[str] = []
```

Purpose:

- Acts as the contract between “planning” and “case writing.”
- Contains the choices a human would want to review: solver, turbulence model,
  velocity, angles, rotor model, assumptions, and missing information.
- Gives future PydanticAI agents a structured output target rather than asking
  them to directly write OpenFOAM files.

This is the most important schema in the project. Future V1/V2 work should
usually add capabilities by enriching or validating this object, not by letting
agent text bypass it.

## OpenFOAM Output Schema

Defined in `src/whittle/models/openfoam.py`.

### `OpenFOAMCaseFiles`

Inventory of planned/written case files.

```python
class OpenFOAMCaseFiles(BaseModel):
    case_dir: Path
    system_files: list[str] = []
    constant_files: list[str] = []
    initial_condition_files: list[str] = []
    files_written: list[str] = []
    warnings: list[str] = []
```

Purpose:

- Makes file generation auditable.
- Separates OpenFOAM directories by their normal roles:
  `system/`, `constant/`, and `0/`.
- Gives tests and future evals a simple way to check completeness.

## Report Schemas

Defined in `src/whittle/models/reports.py`.

### `TraceEvent`

A visible engineering trace event.

```python
class TraceEvent(BaseModel):
    event_type: str
    message: str
    data: dict[str, Any] = {}
```

Purpose:

- Shows what the workflow did without exposing hidden model reasoning.
- Supports UI trace events like `GeometryResolved`, `FilesWritten`, and
  `ValidationRun`.
- Will become more important once PydanticAI orchestration is introduced.

### `CaseSetupReport`

The human-reviewable output of the workflow.

```python
class CaseSetupReport(BaseModel):
    case_name: str
    spec: SimulationCaseSpec
    files_written: list[str] = []
    assumptions: list[str] = []
    warnings: list[str] = []
    missing_information: list[str] = []
    can_run: bool
    why_not_run: str | None = None
    recommended_next_steps: list[str] = []
    trace_events: list[TraceEvent] = []
    validation_checks: list[str] = []
```

Purpose:

- Returns one review object from deterministic tools or future agents.
- Keeps generated files, assumptions, warnings, missing information, and trace
  events together.
- Is the natural object to show in a CLI summary, JSON artifact, eval report,
  or future Streamlit UI.

## Design Notes

- These schemas are deliberately domain-specific. They describe CFD setup
  concepts, not generic agent messages.
- They are also deliberately incomplete. V0 does not yet model actuator disks,
  coordinate transforms, log parsing, convergence state, or post-processing.
- The right growth pattern is: add fields when a test, eval, agent tool, or UI
  genuinely needs them.
- Do not use the Pydantic models as a dumping ground for every possible
  OpenFOAM option. Detailed OpenFOAM dictionary generation should stay inside
  the case writer until a setting needs to become part of the public workflow
  contract.
