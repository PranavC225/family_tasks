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

## Deploy (live setup — done)
Runbook is PLAN.md §14; this is the actual state after following it.

- **Source**: GitHub `PranavC225/family_tasks`, branch `main`. Cloud Build trigger watches `^main$` —
  every push to `main` rebuilds the Dockerfile and deploys a new Cloud Run revision automatically.
  No manual deploy step.
- **GCP project**: `family-tasks` (dedicated, "No organisation"). APIs enabled: Cloud Run Admin,
  Cloud Build.
- **Cloud Run service**: `family-tasks`, region `europe-west4` (Netherlands). Allow public access
  (auth is handled in-app, not by Cloud Run IAM), request-based billing, ingress: all,
  min-instances=0 (free-tier scale-to-zero, accepts cold start).
- **Database**: Neon Postgres, region `eu-central-1` (Frankfurt). Neon Auth is off — unused, the app
  has its own OAuth.
- **Secrets**: `SECRET_KEY`, `DATABASE_URL`, `GOOGLE_CLIENT_SECRET` are in Secret Manager, referenced
  as env vars on the Cloud Run service (not plaintext). The Cloud Run service's default compute
  service account has the `Secret Manager Secret Accessor` role. `ENV`, `BASE_URL`,
  `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS` are plain env vars (non-secret).
- **OAuth consent screen**: External, Testing mode (not published — under 100 test users, no Google
  verification needed). Test users = the 4 family emails, matching `ALLOWED_EMAILS`.
- **Schema changes**: `init_db()` only runs `create_all()` on startup — it creates missing tables but
  does NOT alter existing ones. Changing a model's columns after the first deploy needs a manual
  migration (e.g. `ALTER TABLE` against Neon, or introduce Alembic) — `create_all()` won't do it.

## Releasing a change
Commit locally, `git push origin main` — the Cloud Build trigger picks it up and redeploys
automatically. Watch progress under Cloud Build → History or the Cloud Run service's Revisions tab.
