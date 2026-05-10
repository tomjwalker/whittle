# Physics Envelope

_Last updated: 2026-05-10_

This file explains the CFD scenario envelope that Whittle is allowed to plan
and generate during the early educational prototype. The machine-checkable
version lives in `src/whittle/tools/physics_envelope.py` as a typed
`PhysicsEnvelope`, so deterministic tools, future agents, and evals can use the
same limits.

Current coded limits:

- default cruise speed: 5 m/s
- typical small-quadcopter cruise warning threshold: 20 m/s
- hard early-envelope speed limit: 80 m/s
- default MRF omega: 1000 rad/s
- hard MRF omega limit: 5000 rad/s
- hard attitude limit: 30 degrees per roll/pitch/yaw component

## Coordinate Convention

Whittle uses a simple body-frame convention:

```text
x = forward
y = right
z = up
```

Rigid attitude transforms use one matrix for geometry, rotor centres, rotor
axes, and MRF cylinder endpoints:

```text
point'  = R @ (point - origin) + origin
vector' = R @ vector
```

Positive signs are defined as:

- roll: right side up
- pitch: nose up
- yaw: x axis rotates toward y

The legacy BoxQuadcopter STL assembly has a small baked-in pitch visible in
ParaView. Whittle treats this legacy pose as:

```text
roll = 0, pitch = 0, yaw = 0
```

Additional attitude commands transform the whole legacy assembly from that
pose. V0.2 deliberately does not try to subtract or correct the baked-in CAD
attitude.

## Supported Scenario Progression

### A. Static External Aero

Status: done.

- fixed drone geometry
- steady incompressible external flow
- no rotor model
- `simpleFoam`
- qualitative ParaView sanity check

### B. MRF Rotor Baseline

Status: passed OpenFOAM smoke run.

- same legacy quadcopter geometry
- four MRF cylinder zones around the propellers
- alternating rotor angular velocity signs
- `constant/MRFProperties`
- `system/topoSetDict` creates rotor `cellZone`s after meshing
- matching `MRFProperties` and `topoSetDict` rotor zone names

This is still an educational steady-state approximation. It is not
blade-resolved transient rotor CFD.

MRF cases must run `topoSet` after `snappyHexMesh -overwrite` and before
`simpleFoam`. Without that step, OpenFOAM reads `MRFProperties` but fails with
`cannot find MRF cellZone ...`.

### C. Attitude Transforms

Status: implemented in file generation; pitch-only smoke run passed.

Supported planned cases:

- pitch-only additional transform
- roll-only additional transform
- yaw-only additional transform
- combined roll/pitch/yaw transform

The attitude suite command writes all B/C smoke cases:

```bash
uv run whittle write-attitude-suite --output-root outputs
```

Each transformed case must move these together:

- STL geometry vertices
- MRF zone centres
- MRF zone axes
- MRF cylinder endpoints

C1 pitch acceptance evidence from the first smoke run:

- ParaView overlay showed the transformed assembly in the expected pitched pose.
- `checkMesh` reported transformed nonzero `propFRZone`, `propBRZone`,
  `propFLZone`, and `propBLZone` cell zones.
- `simpleFoam` created `MRF1` through `MRF4` and completed five iterations.

The strongest evidence that MRF zones tracked the transform is the combination
of transformed `constant/MRFProperties`, transformed `system/topoSetDict`
cylinder endpoints, nonzero transformed cell-zone bounding boxes in
`checkMesh`, and successful MRF zone creation in `simpleFoam`.

### D. Differential Rotor Speeds

Status: planned.

Potential scenarios:

- yaw by increasing one diagonal rotor pair and decreasing the opposite pair
- roll by left/right differential thrust proxy
- pitch by front/rear differential thrust proxy

This should be modelled first as different signed `omega` magnitudes in the
MRF zones, then evaluated for whether the approximation is useful.

### E. Hover / Takeoff / Ground Effect

Status: later.

This needs a different problem setup:

- floor/ground plane
- likely larger vertical domain
- different boundary conditions
- stronger rotor modelling assumptions

Do not fold this into the early cruise/external-flow cases.

## Out Of Scope For This Prototype

- weapon, targeting, evasion, or payload-optimisation scenarios
- blade-resolved transient rotor CFD
- automatic CAD redesign
- automatic claims of validated aerodynamic performance
- production mesh-quality guarantees

## Eval Hooks

Early evals should check:

- unsupported scenarios are marked as missing information or out of scope
- MRF requires known rotor centres, axes, radius, height, and omega
- attitude transforms keep rotor axes unit length
- transformed geometry and transformed MRF zones use the same transform origin
- smoke cases use small `max_iterations`
