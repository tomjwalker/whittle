# Public Release Checklist

Use this before making the repository public or sharing it with an interview
panel.

## Secrets And Local Files

- Confirm `git status --short` contains only intentional changes.
- Run a secret scan over tracked files.
- Do not commit `.env`, `.env.*`, solver logs, generated OpenFOAM outputs, or
  private CAD.
- Keep high-fidelity CAD in ignored `cad/` or share it through a separate
  read-only link if needed.

## Public Demo Assets

- The committed `assets/legacy_box_quadcopter/triSurface` files are the split
  quadcopter STLs for reproducible `legacy-box` case generation.
- Keep public-safe UI and ParaView screenshots under `assets/screenshots/`.
- Label ParaView screenshots as visualisations, not validation evidence.

## Commands To Run

```bash
uv sync --extra dev
uv run pytest
uv run ruff check
uv run whittle plan-request "Set up external cruise over a quadcopter at 10 m/s with spinning propellers."
uv run whittle write-case --preset legacy-box --output outputs/public_smoke
```

Optional frontend check:

```bash
cd frontend
npm install
npm run lint
npm run build
```

## Security Posture

- Do not expose the local FastAPI app to the public internet.
- The demo API is intended for localhost only.
- Add authentication, rate limiting, and deployment sandboxing before any hosted
  demo.

## Follow-Up Email Points

- Link the GitHub repo.
- Say the project is deliberately bounded and educational.
- Mention the core pattern: typed state, deterministic tools, validation/evals,
  traces, and human review.
- Call out that the OpenAI key and OpenFOAM/ParaView are optional for reviewing
  the architecture, but useful for the full local demo.
