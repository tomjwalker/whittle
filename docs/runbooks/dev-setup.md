# Development Setup

Update this file as soon as the real stack and commands are known.

## Prerequisites

- Python 3.11+
- `uv`
- Node.js 20+

## Environment Files

- Frontend: `.env.local`
- Backend: `backend/.env`
- Examples: `.env.local.example`, `backend/.env.example`

Never commit secrets.

## Default Commands

```bash
# Python dependencies
uv sync

# Python lint
uv run ruff check

# Python tests
uv run pytest

# Frontend dependencies
npm install

# Frontend dev server
npm run dev

# Frontend lint
npm run lint
```

## Deployment Defaults

- Frontend: Vercel
- Backend: Railway
- Database: Postgres or Supabase-hosted Postgres
- Monitoring: Sentry

## Update Rule

Keep this file grounded in the real repo. If a command changes, update this file in the same change.
