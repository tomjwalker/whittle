# Development Setup

_Last updated: 2026-05-10_

## Prerequisites

- Python 3.11+
- `uv`
- OpenFOAM v2012 in WSL for later solver runs
- ParaView 5.13.2 for later post-processing
- Node.js 20+ for the optional Next.js UI

Observed local paths:

```text
OpenFOAM: \\wsl$\Ubuntu-22.04\opt\OpenFOAM\OpenFOAM-v2012
OpenFOAM cases: \\wsl$\Ubuntu-22.04\home\tjwalker\OpenFOAM\cases
ParaView: C:\Program Files\ParaView 5.13.2\bin\paraview.exe
```

## Environment Files

- `.env` and `.env.*` are ignored, except committed examples.
- Never commit secrets or raw environment contents.
- Backend agent settings live in `backend/.env.example`.
- Frontend settings live in `frontend/.env.local.example`.

For the model-backed planning agent:

```bash
OPENAI_API_KEY=sk-...
WHITTLE_AGENT_MODEL=openai-responses:gpt-5.4-mini
WHITTLE_AGENT_THINKING=medium
```

The default model is `openai-responses:gpt-5.4-mini`, chosen as the current
lower-cost OpenAI mini reasoning-capable option for shake-down. Use
`openai-responses:gpt-5.5` for the more expensive flagship path when needed.

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

# Run deterministic planner eval fixtures
uv run whittle eval-planner

# Run the planning agent. Without OPENAI_API_KEY this uses deterministic fallback.
uv run whittle agent-plan "Set up cruise at 5 m/s with spinning propellers." --case-name agent_demo

# Force deterministic fallback for cheap UI/API testing
uv run whittle agent-plan "Set up cruise at 5 m/s with spinning propellers." --deterministic

# Generate a single-STL V0 case from the local ignored hexacopter asset
uv run whittle write-case --geometry cad/drone_model_hex.stl --geometry-mode single-stl --output outputs/hex_v0 --velocity 10
```

## Local Agent API

Start the FastAPI backend:

```bash
uv run uvicorn whittle.api.app:app --reload --reload-dir src --reload-dir backend --port 8000 --env-file backend/.env
```

Useful endpoints:

```text
GET  http://localhost:8000/health
POST http://localhost:8000/api/plan
POST http://localhost:8000/api/plan/stream
POST http://localhost:8000/api/write-case
```

`/api/plan/stream` emits newline-delimited JSON events for the UI.

## Local Next.js UI

The UI is under `frontend/`.

```bash
cd frontend
copy .env.local.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. The UI talks to
`NEXT_PUBLIC_WHITTLE_API_URL`, defaulting to `http://localhost:8000`.

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
