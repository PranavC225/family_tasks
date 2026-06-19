# family-tasks

Private shared to-do app for a family of 4. FastAPI + HTMX (server-rendered), SQLModel over a
DB-agnostic `DATABASE_URL` (SQLite local, Neon Postgres prod), Google OAuth restricted to a
4-email allowlist. Containerized for Google Cloud Run (free tier). Mobile-first.

## Lifecycle
Active → (complete) → Done → (reactivate) → Active. Any task → (archive) → Archived → (unarchive) → Active.
"Done" = removed from the active list but retained. "Archived" = permanent storage.

## Rules
- uv only (never pip/poetry directly). Run: `uv run uvicorn family_tasks.main:app --reload`.
- Keep DB access DB-agnostic — never write SQLite- or Postgres-specific SQL.
- Auth is the email allowlist in `ALLOWED_EMAILS`; the access gate lives in `auth.py:auth_callback`.
- ruff + mypy (strict) + pytest must stay green. Conventional Commits.
- Never commit `.env` or `*.db`. Never push to remote without explicit instruction.

## Run locally without Google
Set `ENV=development` and visit `/auth/dev-login`.

## Deploy
See PLAN.md §14 (Cloud Run + Neon + OAuth runbook).
