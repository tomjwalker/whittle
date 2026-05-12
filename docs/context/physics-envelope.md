# Physics Envelope

_Last updated: 2026-05-12_

This file explains the CFD scenario envelope that Whittle is allowed to plan
and generate during the early educational prototype. The machine-checkable
version lives in `src/whittle/tools/physics_envelope.py` as a typed
`PhysicsEnvelope`, so deterministic tools, future agents, and evals can use the
same limits.

Current coded limits:

- default cruise speed: 5 m/s
- typical small-quadcopter cruise warning threshold: 20 m/s
- hard early-envelope speed limit: 80 m/s
- default rotor omega: 1000 rad/s
- hard rotor omega limit: 5000 rad/s
- hard attitude limit: 30 degrees per roll/pitch/yaw component
- zero freestream is allowed only for static/differential MRF or rotor-disk
  proxy cases

## Performance Guidance MVP

Whittle now has a deliberately simple performance-guidance tool in
`src/whittle/tools/performance_guidance.py`.

It is a small explicit cruise-speed table plus linear interpolation. The table
returns:

- a recommended baseline pitch angle;
- a baseline signed MRF omega for FL, FR, BL/RL, and BR/RR propellers;
- a small pitch/omega sweep for later trim exploration;
- an optional yaw-rate proxy that perturbs opposite rotor pairs for future
  differential-rotor modelling.

The same module now also contains `get_motion_rotor_command`, a typed MVP
motion map from:

```text
u, v, w, roll, pitch, yaw, roll_dot, pitch_dot, yaw_dot
```

to signed FL/FR/BL/BR rotor speeds in rad/s. This is not kriging, a Gaussian
process, or a learned controller. It is an auditable lookup/interpolation plus
bounded additive roll/pitch/yaw-rate differentials. The frontend and agent can
use it to explain and draft bespoke manoeuvre proxies without pretending that
Whittle has solved vehicle trim or flight dynamics.

This is the right MVP because the current project has almost no calibration
data. A Gaussian process, kriging model, or learned surrogate would only become
defensible after we have enough CFD or flight-data points to justify fitting a
model and exposing uncertainty. Until then, transparent table interpolation is
easier to audit in an interview and safer for lay-user guidance.

The tool must not be described as a solved trim model. It gives expert defaults
for case planning and sweep design, then CFD force/moment outputs are used to
judge whether the point is balanced.

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

### B2. Static Hover MRF Smoke

Status: implemented as a caveated planning/writer case.

- zero freestream
- zero/default attitude unless the user specifies otherwise
- MRF rotors enabled
- no floor, ground effect, takeoff transient, or solved trim claim

This is allowed because it is useful as a quick educational rotor/downwash
smoke case. It must be labelled as an approximation, not as validated hover
performance.

### B3. Rotor-Disk Source-Term Downwash Case

Status: implemented for the legacy quadcopter.

- four `rotorDisk` `fvOptions` source terms
- same `topoSetDict` cylinder-to-`cellZone` workflow as MRF
- stronger induced-flow/downwash-oriented approximation than plain MRF
- still steady `simpleFoam`, not blade-resolved AMI/sliding-mesh CFD
- must inspect downwash sign and source strength in ParaView

This is the current best overnight fidelity step when the visual failure mode
is weak propeller downwash. It keeps the existing meshing workflow but adds a
momentum source in the rotor zones. The writer generates `system/fvOptions`
plus `system/topoSetDict`; `Allrun` executes `topoSet` before `simpleFoam`.

Example:

```bash
uv run whittle write-case --preset legacy-box --rotor-model rotor-disk \
  --velocity 0 --mrf-omega-rad-s 1200 --max-iterations 500 \
  --write-interval 100 --case-name legacy_box_rotor_disk_hover_t500 \
  --output outputs/legacy_box_rotor_disk_hover_t500
```

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

Status: implemented as a caveated steady MRF proxy.

Potential scenarios:

- yaw by increasing one diagonal rotor pair and decreasing the opposite pair
- roll by left/right differential thrust proxy
- pitch by front/rear differential thrust proxy

This is modelled first as different signed `omega` magnitudes in the MRF zones.
The planner labels these cases as `steady_incompressible_motion_proxy_mrf` and
keeps the key caveat visible: roll_dot, pitch_dot, and yaw_dot are not imposed
as body angular velocities in `simpleFoam`; they are converted into a steady
differential rotor-speed proxy.

Rotor-disk can use the same per-rotor omega map, but the agent should present
it as a source-term fidelity tradeoff: more visible induced flow, more
heuristic force modelling.

### E. Floor / Takeoff / Ground Effect

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
