# Development Setup

_Last updated: 2026-05-10_

## Prerequisites

- Python 3.11+
- `uv`
- OpenFOAM v2012 in WSL for later solver runs
- ParaView 5.13.2 for later post-processing

Observed local paths:

```text
OpenFOAM: \\wsl$\Ubuntu-22.04\opt\OpenFOAM\OpenFOAM-v2012
OpenFOAM cases: \\wsl$\Ubuntu-22.04\home\tjwalker\OpenFOAM\cases
ParaView: C:\Program Files\ParaView 5.13.2\bin\paraview.exe
```

## Environment Files

- `.env` and `.env.*` are ignored, except committed examples.
- Never commit secrets or raw environment contents.

## Python Commands

```bash
# Install dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Lint
uv run ruff check

# Generate the legacy split-surface V0 case
uv run whittle write-case --preset legacy-box --output outputs/legacy_box_v0

# Generate a short smoke-run case for OpenFOAM shakedown
uv run whittle write-case --preset legacy-box --output outputs/legacy_box_smoke --max-iterations 50 --write-interval 10

# Generate a 5-iteration legacy MRF smoke case
uv run whittle write-case --preset legacy-box --rotor-model mrf --mrf-omega-rad-s 1000 --max-iterations 5 --write-interval 5 --output outputs/legacy_box_mrf_smoke

# Generate a 5-iteration pitch-transformed MRF smoke case
uv run whittle write-case --preset legacy-box --rotor-model mrf --mrf-omega-rad-s 1000 --pitch-deg 10 --max-iterations 5 --write-interval 5 --output outputs/legacy_box_mrf_pitch10_smoke

# Generate all B/C attitude smoke cases
uv run whittle write-attitude-suite --output-root outputs --velocity 5 --mrf-omega-rad-s 1000 --max-iterations 5 --write-interval 5

# Deterministically plan a rough user request before writing a case
uv run whittle plan-request "Set up external cruise over a quadcopter at 10 m/s with spinning propellers."

# Generate a single-STL V0 case from the local ignored hexacopter asset
uv run whittle write-case --geometry cad/drone_model_hex.stl --geometry-mode single-stl --output outputs/hex_v0 --velocity 10
```

## OpenFOAM Activation

From PowerShell:

```powershell
wsl -d Ubuntu-22.04
```

Inside Ubuntu:

```bash
source /opt/OpenFOAM/OpenFOAM-v2012/etc/bashrc
which simpleFoam
which blockMesh
which snappyHexMesh
```

V0 writes case files only. Solver execution is intentionally a later explicit
step.

## Manual OpenFOAM Run With Logs

For long solver runs, write logs inside the WSL case directory rather than
copying terminal output back into chat:

```bash
cd ~/OpenFOAM/cases/legacy_box_v0
mkdir -p run_logs

blockMesh 2>&1 | tee run_logs/blockMesh_$(date +%Y%m%d_%H%M%S).log
snappyHexMesh -overwrite 2>&1 | tee run_logs/snappyHexMesh_$(date +%Y%m%d_%H%M%S).log
checkMesh 2>&1 | tee run_logs/checkMesh_$(date +%Y%m%d_%H%M%S).log
simpleFoam 2>&1 | tee run_logs/simpleFoam_$(date +%Y%m%d_%H%M%S).log
```

For MRF cases, `topoSet` is required after meshing so the rotor-cylinder
`cellSet`s become the `cellZone`s referenced by `constant/MRFProperties`:

```bash
cd ~/OpenFOAM/cases/legacy_box_mrf_smoke
mkdir -p run_logs

blockMesh 2>&1 | tee run_logs/blockMesh_$(date +%Y%m%d_%H%M%S).log
snappyHexMesh -overwrite 2>&1 | tee run_logs/snappyHexMesh_$(date +%Y%m%d_%H%M%S).log
topoSet 2>&1 | tee run_logs/topoSet_$(date +%Y%m%d_%H%M%S).log
checkMesh 2>&1 | tee run_logs/checkMesh_$(date +%Y%m%d_%H%M%S).log
simpleFoam 2>&1 | tee run_logs/simpleFoam_$(date +%Y%m%d_%H%M%S).log
```

Later Whittle should gain a typed log parser for `checkMesh` and solver status.
Until then, keep large logs local and ignored.

## Update Rule

If the real command changes, update this file in the same change.
