# Development Setup

_Last updated: 2026-05-09_

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

Later Whittle should gain a typed log parser for `checkMesh` and solver status.
Until then, keep large logs local and ignored.

## Update Rule

If the real command changes, update this file in the same change.
