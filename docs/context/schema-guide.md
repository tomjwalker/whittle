# Schema Guide

_Last updated: 2026-05-10_

Whittle uses Pydantic models as explicit workflow state. The important idea is
that the project should not pass around anonymous dictionaries or hidden LLM
text. Each stage receives and returns typed objects that can be validated,
serialized, tested, evaluated, and shown to a human reviewer.

The current schemas describe geometry, rotor modelling, simulation intent,
OpenFOAM file output, and the human-reviewable report.

## Current Data Flow

```text
STL files
  -> StlMetadata
  -> GeometrySurfaceSpec
  -> DroneGeometrySpec
  -> MRFZoneSpec when requested
  -> PhysicsEnvelope validation
  -> BoundaryConditionPlan
  -> SimulationCaseSpec
  -> OpenFOAM case writer
  -> CaseSetupReport + TraceEvent list
```

In V1, the front of this chain will start from a natural-language request:

```text
messy user request
  -> ScenarioIntent / motion-command planning layer
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
- Gives future evals deterministic facts to check, such as "large STL warning
  is present."

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

## Rotor Schemas

Defined in `src/whittle/models/rotors.py`.

### `MRFZoneSpec`

One Multiple Reference Frame volume zone around one propeller.

```python
class MRFZoneSpec(BaseModel):
    name: str
    cell_zone: str
    cylinder_name: str
    centre_m: tuple[float, float, float]
    axis: tuple[float, float, float]
    radius_m: float
    height_m: float
    omega_rad_s: float
    source_patch: str | None = None
    notes: list[str] = []
```

Purpose:

- Keeps rotor centres, axes, cylinder dimensions, and signed angular speed in
  typed state.
- Lets the case writer generate `snappyHexMeshDict` searchable cylinders,
  `system/topoSetDict` cell-zone creation, and `constant/MRFProperties` from
  the same source of truth.
- Makes attitude transforms testable before OpenFOAM is run.

### `RotorAssemblySpec`

Small grouping object for future rotor models.

```python
class RotorAssemblySpec(BaseModel):
    model: str
    zones: list[MRFZoneSpec] = []
    notes: list[str] = []
```

Purpose:

- Reserved for the point where rotor modelling grows beyond a flat list on
  `SimulationCaseSpec`.

### `RotorDiskSourceSpec`

Typed OpenFOAM `rotorDisk` `fvOptions` source around one propeller.

Purpose:

- Reuses the legacy propeller centres and rotor-zone cell names.
- Generates searchable cylinder regions, `topoSet` cell zones, and
  `system/fvOptions` from one typed source.
- Gives the planner an explicit MRF-vs-rotor-disk fidelity tradeoff: MRF is
  cheaper/conservative; rotor-disk source terms are better for visible
  downwash but more heuristic.

## Planning Schemas

Defined in `src/whittle/models/planning.py`.

### `PhysicsEnvelope`

Machine-checkable limits for the early CFD demo.

Purpose:

- Keeps speed, attitude, and MRF omega limits in typed code rather than only in
  prose.
- Lets validation and future evals reject or warn on scenarios outside the
  current OpenFOAM writer's intended envelope.
- Gives the future agent a compact policy object: what it is allowed to plan,
  what it should ask about, and what it should mark as out of scope.

### `ScenarioPlan`

Output of the deterministic pre-agent planning layer.

Purpose:

- Captures the upstream state before case writing: scenario type, extracted
  `SimulationCaseSpec`, assumptions, warnings, missing information, clarifying
  questions, and visible trace events.
- Acts as the first non-LLM rehearsal for the later PydanticAI workflow.
- Is a natural response object for a chat UI: the user sees what was extracted
  and what still needs clarification.

### `MotionIntent` And `MotionRotorCommand`

Defined in `src/whittle/tools/performance_guidance.py`.

Purpose:

- Represents bespoke manoeuvre requests before they become case files:
  `u`, `v`, `w`, roll/pitch/yaw, and roll/pitch/yaw rates.
- Converts those inputs through a transparent heuristic table/function into
  signed FL/FR/BL/BR MRF rotor speeds.
- Lets the agent discuss yawing, rolling, pitching, or combined manoeuvres with
  a lay user while keeping the caveat explicit: this is a steady differential
  MRF proxy, not a solved flight-dynamics controller.

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
    rotor_model: Literal["none", "actuator_disk_placeholder", "mrf", "rotor_disk"] = "none"
    mrf_zones: list[MRFZoneSpec] = []
    rotor_disk_sources: list[RotorDiskSourceSpec] = []
    solver_family: str = "simpleFoam"
    turbulence_model: str = "kOmegaSST"
    mesh_strategy: str = "blockMesh background mesh with snappyHexMesh surface snapping"
    kinematic_viscosity_m2_s: float = 1.5e-5
    air_density_kg_m3: float = 1.225
    max_iterations: int = 500
    write_interval: int = 100
    transform_origin_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    missing_information: list[str] = []
    assumptions: list[str] = []
    validation_checks: list[str] = []
```

Purpose:

- Acts as the contract between "planning" and "case writing."
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
  or future Streamlit/Next.js UI.

## Design Notes

- These schemas are deliberately domain-specific. They describe CFD setup
  concepts, not generic agent messages.
- They are also deliberately incomplete. V0.2 models MRF zones, rotor-disk
  source terms, and rigid transforms, but not blade-resolved transient rotor
  CFD, convergence state, or post-processing.
- The right growth pattern is: add fields when a test, eval, agent tool, or UI
  genuinely needs them.
- Do not use the Pydantic models as a dumping ground for every possible
  OpenFOAM option. Detailed OpenFOAM dictionary generation should stay inside
  the case writer until a setting needs to become part of the public workflow
  contract.
