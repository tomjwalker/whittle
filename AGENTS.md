# [PROJECT_NAME] - Agent Guardrails

This file is the canonical working contract for coding agents in this repository.

Codex auto-discovers `AGENTS.md`. Keep this file short, high-signal, and current. Use it to point to the few docs that matter.

## Start Here

- `docs/context/overview.md` - product, architecture, constraints, priorities
- `docs/runbooks/dev-setup.md` - local commands, setup, deployment notes
- `docs/planning/current-plan.md` - the current multi-step initiative
- `docs/planning/brainstorm-backlog.md` - ideas and hypotheses worth retaining
- `docs/decisions/0000-template.md` - template for durable architectural or product decisions

## Default Implementation Bias

If the project has no stronger constraint, prefer:

- Python backend
- FastAPI
- Pydantic
- PydanticAI when agent or tool orchestration is useful
- Postgres
- Supabase when hosted auth, storage, or realtime help materially
- Next.js frontend
- TypeScript
- Tailwind CSS
- shadcn/ui
- Railway for backend deployment
- Vercel for frontend deployment
- Sentry for monitoring
- `uv` for Python package management
- `Ruff` for Python linting and formatting

Do not re-open every stack decision from scratch unless requirements justify it.

## Workflow Expectations

1. Orient first. Read the overview and relevant runbooks before editing.
2. Plan before editing on non-trivial tasks.
3. Prefer minimal, high-leverage diffs.
4. Run relevant checks when safe.
5. Explain what changed, why, and how it was validated.
6. Escalate uncertainty instead of guessing on risky work.

## Planning And Brainstorming Rules

- Keep small or disposable thinking in chat.
- Persist markdown only when the context should survive a thread.
- Keep one active plan by default in `docs/planning/current-plan.md`.
- Use `docs/planning/brainstorm-backlog.md` for ideas, hypotheses, and open questions.
- Create a decision record from `docs/decisions/0000-template.md` only when the choice is likely to matter later.
- Use GitHub Issues or Projects for ownership, prioritization, and status.
- If the repo becomes research-heavy, add a `research/` directory for raw sources, synthesized notes, and reusable outputs.

## Non-Negotiable Guardrails

- Never log, copy, or commit secrets or raw `.env` contents.
- Do not mutate production systems without explicit confirmation.
- Do not perform destructive filesystem, git, or data operations without explicit confirmation.
- Treat user and customer data as sensitive.
- Escalate before changing auth, billing, permissions, rate limits, or data retention.

## Engineering Defaults

- Prefer typed code and explicit schemas.
- Prefer config-driven behavior over hard-coded values.
- Fail fast with clear errors when required configuration is missing.
- Keep adapters and integrations narrowly scoped.
- Keep logs purposeful and avoid dumping whole payloads in production paths.
- Add or update tests when they materially reduce risk.

## Verification Expectations

- Docs-only changes: run available lint or link checks.
- Backend changes: run the relevant tests and linting.
- Frontend changes: run lint plus relevant UI or unit tests.
- Prompt or AI behavior changes: run fixtures, evals, or representative smoke tests where available.
- Record what was run and what was skipped.

## When Stuck

Stop, summarize the blocker, and ask `[OWNER_NAME]` for guidance.
