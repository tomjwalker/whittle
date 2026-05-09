# GitHub Cold-Start Template

This is the lean default template for new Tom projects.

It is designed to be:

- minimal at the repo root
- immediately useful to Codex
- good for brainstorming before code
- strong enough for real delivery once implementation starts

## Root Philosophy

Keep the root simple.

Codex auto-discovers `AGENTS.md`. Everything else should be linked from there instead of relying on extra root-level AI files.

## Canonical Bundle

This is the default bundle I would use for most new repos.

## What Lives At The Root

- `AGENTS.md` - the canonical instructions file for Codex and other coding agents
- `README.md` - the human overview and setup pointer
- `.gitignore`
- `.editorconfig`
- `.github/pull_request_template.md`
- `.env.local.example` and `backend/.env.example` if using the preferred Next.js + FastAPI shape

## What Lives Under `docs/`

- `docs/context/overview.md` - product, architecture, constraints, priorities
- `docs/runbooks/dev-setup.md` - local setup, commands, deploy notes
- `docs/planning/current-plan.md` - one live multi-step initiative
- `docs/planning/brainstorm-backlog.md` - ideas and hypotheses worth keeping
- `docs/decisions/0000-template.md` - durable decision records when needed

## Optional Later Additions

- `research/` if the repo becomes source-heavy or knowledge-compounding
- more decision records under `docs/decisions/`
- more runbooks only when a subsystem becomes risky or non-obvious

Do not add these by default unless the repo actually needs them.

## First-Hour Setup

1. Replace the placeholders in `AGENTS.md` and `docs/context/overview.md`.
2. Write the real product and architecture context.
3. Trim any sections you know you will not use.
4. Add the actual commands to `docs/runbooks/dev-setup.md`.
5. Put the current initiative in `docs/planning/current-plan.md`.
6. Ask Codex to review the template and remove any dead weight.

## Planning Rules

Use chat for:

- disposable brainstorming
- small questions
- short-lived exploration

Use markdown for:

- context that should survive the thread
- active multi-step plans
- ideas worth revisiting
- decisions that future agents should not rediscover
- research notes that should compound over time once a `research/` lane exists

Use GitHub Issues or Projects for:

- ownership
- prioritization
- backlog status
- milestone tracking

## How To Turn This Into A Real GitHub Template

Create a new repository, copy this directory into its root, push it, then mark the repository as a template in GitHub Settings.

GitHub's current docs say:

- repository admins can mark a repo as a template
- users with read access can then create new repos from `Use this template`
- repos created from a template start as a separate new repository rather than sharing commit history with the template

Sources:

- [Creating a template repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-template-repository)
- [Creating a repository from a template](https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-repository-from-a-template)
